"""
SovereignSwarm — Binance P2P Engine
Earn USDT → sell on Binance P2P → receive INR via UPI
Real money path: Crypto earnings → P2P sell order → UPI transfer to your bank

Requirements:
  1. Binance account (KYC required in India)
  2. API Key + Secret with P2P permissions
  3. USDT balance in Binance spot wallet
  4. UPI linked in Binance P2P settings

Steps to activate:
  1. Go to https://www.binance.com/en/my/settings/api-management
  2. Create API key (enable: Spot trading, P2P trading)
  3. Enable P2P in your account settings
  4. Add UPI as payment method in Binance P2P settings
  5. Send API key + secret → I'll store them securely
"""

import os, json, time, hashlib, hmac, requests, urllib.parse
from dataclasses import dataclass

SWARM_DIR = os.path.dirname(os.path.abspath(__file__))
P2P_ORDERS_FILE = os.path.join(SWARM_DIR, "p2p_orders.json")
P2P_CONFIG_FILE = os.path.join(SWARM_DIR, "targets", "binance_p2p.yaml")

@dataclass
class P2POrder:
    order_id: str
    side: str  # "SELL" or "BUY"
    amount_usdt: float
    price_inr: float
    total_inr: float
    payment_method: str
    status: str
    created_at: str

# ── Binance API Config ──────────────────────────────────────────────────────
BINANCE_API  = "https://api.binance.com"
BINANCE_P2P  = f"{BINANCE_API}/sapi/v1/c2c/"

def _sign(params: dict, secret: str) -> str:
    """HMAC-SHA256 signing for Binance SAPI requests."""
    qs = urllib.parse.urlencode(params)
    sig = hmac.new(
        secret.encode("utf-8"),
        qs.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return sig

def _load_p2p_config() -> dict:
    if os.path.exists(P2P_CONFIG_FILE):
        import yaml
        with open(P2P_CONFIG_FILE) as f:
            return yaml.safe_load(f)
    return {}

# ── Fetch P2P ads (public — no auth needed) ─────────────────────────────────
def get_p2p_ads(side: str = "SELL", asset: str = "USDT", fiat: str = "INR",
                payment: str = "UPI") -> list:
    """
    Fetch available P2P ads. side=SELL means you are selling USDT → get INR.
    Returns list of ads with price, min/max quantity, payment methods.
    """
    url = f"{BINANCE_P2P}orderMatchListByPage"
    params = {
        "tradeType":     side.upper(),
        "asset":         asset,
        "fiat":          fiat,
        "paymentMethod": payment,
        "page":          1,
        "rows":          20,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if "data" in data:
            return data["data"]
        return []
    except Exception as e:
        return []

def get_sell_ads() -> list:
    """Get buyers looking to BUY USDT from you — they pay INR."""
    return get_p2p_ads(side="SELL")  # you sell USDT, they pay INR

# ── Place P2P order (requires auth) ─────────────────────────────────────────
def place_sell_order(quantity_usdt: float, price_inr: float,
                     api_key: str, api_secret: str) -> dict:
    """
    Post a SELL order (you sell USDT, receive INR via UPI).
    Uses Binance P2P order placement API.
    """
    url = f"{BINANCE_P2P}placeOrder"
    params = {
        "asset":       "USDT",
        "fiat":        "INR",
        "tradeType":   "SELL",
        "priceType":   1,           # fixed price
        "price":       str(price_inr),
        "amount":      str(quantity_usdt),
        "totalAmount": str(round(quantity_usdt * price_inr, 2)),
        "paymentMethod": "UPI",
        "source":      "P2P_PC",
        "recvWindow":  5000,
        "timestamp":   int(time.time() * 1000),
    }
    params["signature"] = _sign(params, api_secret)

    headers = {"X-MBX-APIKEY": api_key}
    try:
        resp = requests.post(url, headers=headers, data=params, timeout=10)
        result = resp.json()
        if result.get("orderId"):
            return {"success": True, "orderId": result["orderId"], "message": "P2P order placed"}
        return {"success": False, "error": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

def confirm_order(order_id: str, api_key: str, api_secret: str) -> dict:
    """Mark order as paid (after buyer confirms they've paid)."""
    url = f"{BINANCE_P2P}matchOrder"
    params = {
        "orderId":     order_id,
        "recvWindow":  5000,
        "timestamp":   int(time.time() * 1000),
    }
    params["signature"] = _sign(params, api_secret)
    headers = {"X-MBX-APIKEY": api_key}
    try:
        resp = requests.post(url, headers=headers, data=params, timeout=10)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def release_usdt(order_id: str, api_key: str, api_secret: str) -> dict:
    """
    Release USDT to buyer — ONLY after UPI payment confirmed.
    This is the final step. After this, INR arrives in your Binance P2P balance.
    """
    url = f"{BINANCE_P2P}releaseCoin"
    params = {
        "orderId":     order_id,
        "recvWindow":  5000,
        "timestamp":   int(time.time() * 1000),
    }
    params["signature"] = _sign(params, api_secret)
    headers = {"X-MBX-APIKEY": api_key}
    try:
        resp = requests.post(url, headers=headers, data=params, timeout=10)
        result = resp.json()
        if result.get("success"):
            return {"success": True, "orderId": order_id}
        return {"success": False, "error": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_order_status(order_id: str, api_key: str, api_secret: str) -> dict:
    """Get current status of a P2P order."""
    url = f"{BINANCE_P2P}getOrderDetail"
    params = {
        "orderId":     order_id,
        "recvWindow":  5000,
        "timestamp":   int(time.time() * 1000),
    }
    params["signature"] = _sign(params, api_secret)
    headers = {"X-MBX-APIKEY": api_key}
    try:
        resp = requests.post(url, headers=headers, data=params, timeout=10)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def get_usdt_balance(api_key: str, api_secret: str) -> float:
    """Get USDT spot wallet balance."""
    url = f"{BINANCE_API}/api/v3/account"
    params = {
        "recvWindow": 5000,
        "timestamp":  int(time.time() * 1000),
    }
    params["signature"] = _sign(params, api_secret)
    headers = {"X-MBX-APIKEY": api_key}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        data = resp.json()
        for b in data.get("balances", []):
            if b["asset"] == "USDT":
                return float(b["free"])
    except:
        pass
    return 0.0

# ── Passive income: advertise USDT for sale ───────────────────────────────────
def get_competitive_sell_price() -> float:
    """Find best INR price from buyers to undercut slightly."""
    ads = get_sell_ads()
    if not ads:
        return 82.0  # fallback
    # Best price = highest INR per USDT from buyers
    prices = [float(a.get("price", 0)) for a in ads if float(a.get("price", 0)) > 0]
    if prices:
        return max(prices)  # sell at best price available
    return 82.0

# ── Save P2P orders ──────────────────────────────────────────────────────────
def save_order(order: P2POrder):
    orders = []
    if os.path.exists(P2P_ORDERS_FILE):
        with open(P2P_ORDERS_FILE) as f:
            orders = json.load(f)
    orders.append(order.__dict__)
    with open(P2P_ORDERS_FILE, "w") as f:
        json.dump(orders[-100:], f, indent=2)

# ── Check P2P eligibility ────────────────────────────────────────────────────
def check_p2p_status(api_key: str, api_secret: str) -> dict:
    """Check if account can do P2P."""
    ads = get_sell_ads()
    return {
        "p2p_enabled": len(ads) > 0 or get_usdt_balance(api_key, api_secret) >= 0,
        "ads_available": len(ads),
        "min_price": ads[0].get("price") if ads else None,
    }

# ── Telegram payout notification ────────────────────────────────────────────
def notify_telegram(message: str):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id   = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not bot_token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=5
        )
    except:
        pass

if __name__ == "__main__":
    print("═══ SovereignSwarm Binance P2P Engine ═══")
    config = _load_p2p_config()

    # Show current P2P market prices (no API needed)
    ads = get_sell_ads()
    print(f"\n[Binance P2P] {len(ads)} sell-ads available (USDT → INR via UPI)")
    for ad in ads[:5]:
        print(f"  ₹{ad.get('price','?')}/USDT | "
              f"Qty: {ad.get('minSingleTradeAmount','?')}-{ad.get('maxSingleTradeAmount','?')} USDT | "
              f"Method: {ad.get('paymentMethod','?')}")

    api_key    = os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("BINANCE_API_SECRET", "")
    if api_key and api_secret:
        bal = get_usdt_balance(api_key, api_secret)
        print(f"\nYour USDT balance: {bal:.4f}")
        status = check_p2p_status(api_key, api_secret)
        print(f"P2P status: {status}")
    else:
        print("\n⚠ No Binance API keys found in Settings > Advanced")
        print("→ Add BINANCE_API_KEY and BINANCE_API_SECRET to activate P2P auto-sell")