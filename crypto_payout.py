"""
SovereignSwarm — Crypto Payout Engine
Supports BNB Smart Chain (BEP20), TRON (TRC20), Ethereum (ERC20).
Owner sets their wallet address in config.yaml. Private key goes in Zo Settings.
"""
import os, json, time, yaml
from datetime import datetime
from dataclasses import dataclass

# ── Paths ──────────────────────────────────────────────────────────────────────
_SWARM_DIR = os.path.dirname(os.path.abspath(__file__))
LEDGER_FILE = os.path.join(_SWARM_DIR, "payout_ledger.json")
CONFIG_FILE = os.path.join(_SWARM_DIR, "config.yaml")

# ── Load owner config from config.yaml ───────────────────────────────────────
def _load_config() -> dict:
    try:
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f)
    except Exception:
        return {}

_CONFIG = _load_config()

# ── Network definitions ────────────────────────────────────────────────────────
NETWORKS = {
    "bnb": {
        "name":     "BNB Smart Chain",
        "token":    "BNB",
        "rpc_url":   os.environ.get("BNB_RPC_URL", "https://bsc-dataseed.binance.org/"),
        "chain_id": 56,
        "explorer": "https://bscscan.com",
        "min_payout_usd": 5.0,
        "gas_units": 21000,
    },
    "tron": {
        "name":     "TRON",
        "token":    "TRX",
        "rpc_url":   "https://api.trongrid.io",
        "chain_id":  728126421,
        "explorer": "https://tronscan.org",
        "min_payout_usd": 10.0,
        "gas_units": 0,
    },
    "eth": {
        "name":     "Ethereum",
        "token":    "ETH",
        "rpc_url":   os.environ.get("ETH_RPC_URL", "https://rpc.ankr.com/eth"),
        "chain_id":  1,
        "explorer":  "https://etherscan.io",
        "min_payout_usd": 10.0,
        "gas_units": 21000,
    },
}

PAYPAL_EMAIL = os.environ.get("PAYPAL_EMAIL", "")
WISE_API_KEY = os.environ.get("WISE_API_KEY", "")

# ── Owner wallet address (from config.yaml) ───────────────────────────────────
BNB_RECEIVING_ADDRESS = os.environ.get(
    "BNB_RECEIVING_ADDRESS",
    _CONFIG.get("crypto", {}).get("bnb_receiving_address", "")
).strip()

# ── BNB Chain Config ────────────────────────────────────────────────────────
BNB_CFG_FILE = os.path.join(os.path.dirname(__file__), "config.yaml")
BNB_SECRETS_FILE = os.path.join(os.path.dirname(__file__), ".secrets", "secrets.enc")

def _load_bnb_config() -> dict:
    try:
        with open(BNB_CFG_FILE) as f:
            raw = yaml.safe_load(f)
        return raw.get("crypto", {}) or {}
    except Exception:
        return {}

def _load_bnb_secrets() -> dict:
    secrets = {}
    if os.path.exists(BNB_SECRETS_FILE):
        with open(BNB_SECRETS_FILE) as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    secrets[k] = v
    return secrets

# ── Sender private key (from Zo Settings secrets — never hardcoded) ──────────
def _sender_privkey() -> str:
    # 1. Environment variable (set by Zo Settings > Advanced)
    env_key = os.environ.get("BNB_PRIVATE_KEY", "").strip()
    if env_key:
        return env_key
    # 2. Local .secrets file (fallback for self-hosted)
    secrets = _load_bnb_secrets()
    return secrets.get("BNB_PRIVATE_KEY", "")

# ── Ledger ──────────────────────────────────────────────────────────────────
def _load_ledger() -> dict:
    if os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE) as f:
            return json.load(f)
    return {"payouts": [], "pending": [], "failed": []}

def _save_ledger(ledger: dict):
    with open(LEDGER_FILE, "w") as f:
        json.dump(ledger, f, indent=2)

def _add_payout(entry: dict):
    ledger = _load_ledger()
    ledger["payouts"].append(entry)
    _save_ledger(ledger)

# ── Gas estimator ──────────────────────────────────────────────────────────
def _estimate_gas_usd(network: str, gas_units: int) -> float:
    """
    Estimate the USD cost of a BNB gas fee. Returns 0 if RPC is unreachable.
    Caches the Web3 instance to avoid reconnecting every call.
    """
    from web3 import Web3 as W3
    rpc_url = NETWORKS[network]["rpc_url"]
    try:
        w3 = W3(W3.HTTPProvider(rpc_url))
        gas_price = w3.eth.gas_price
        bal_wei   = w3.eth.get_balance(_SENDER_WALLET)
        bal_bnb   = w3.from_wei(bal_wei, "ether")
        fee_bnb   = gas_price * gas_units / 1e18
        fee_usd   = fee_bnb * _get_bnb_price()
        if fee_usd > bal_bnb:
            return 0.0  # not enough BNB to pay this fee
        return fee_usd
    except Exception as e:
        print(f"  [gas-estimate] RPC unreachable ({rpc_url}) — assuming $0 fee: {e}")
        return 0.0

def _get_token_price_usd(token: str) -> float:
    """Get token price in USD from CoinGecko (free API, no key)."""
    key = f"_price_{token}"
    cached = getattr(_get_token_price_usd, key, None)
    now = time.time()
    if cached and now - cached[0] < 120:
        return cached[1]
    try:
        import requests
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "binancecoin", "vs_currencies": "usd"},
            timeout=5,
        )
        price = r.json().get("binancecoin", {}).get("usd", 0)
        _get_token_price_usd._price_BNB = (now, price)
        return price
    except Exception:
        return 600.0  # fallback BNB price

# ── BNB Smart Chain transfer ────────────────────────────────────────────────
def _bnb_transfer(to_address: str, amount_usd: float, privkey: str) -> dict:
    """Send BNB (or BEP20 USDT) to `to_address`. Amount in USD equivalent."""
    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(NETWORKS["bnb"]["rpc_url"]))
        if not w3.is_connected():
            return {"success": False, "error": "bnb_rpc_unreachable"}

        account   = w3.eth.account.from_key(privkey)
        nonce     = w3.eth.get_transaction_count(account.address)
        gas_price = w3.eth.gas_price

        # Convert USD → BNB using live price
        bnb_price = _get_token_price_usd("BNB")
        amount_bnb = amount_usd / bnb_price
        gas_cost_bnb = gas_price * NETWORKS["bnb"]["gas_units"]
        amount_after_gas = w3.from_wei(amount_bnb * 1e18 - gas_cost_bnb, "ether")

        if amount_after_gas < 0.001:
            return {"success": False, "error": f"amount_too_small_after_gas"}

        tx = {
            "to":       Web3.to_checksum_address(to_address),
            "value":    w3.to_wei(max(amount_after_gas, 0.001), "ether"),
            "gas":      NETWORKS["bnb"]["gas_units"],
            "gasPrice": gas_price,
            "nonce":    nonce,
            "chainId":  56,
        }
        signed  = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        return {
            "success":      True,
            "tx_hash":      tx_hash.hex(),
            "explorer_url": f"https://bscscan.com/tx/{tx_hash.hex()}",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── USDT BEP20 transfer ───────────────────────────────────────────────────
def _usdt_transfer(to_address: str, amount_usd: float, privkey: str) -> dict:
    """Send USDT (BEP20) via BNB Smart Chain."""
    try:
        from web3 import Web3
        from eth_abi import encode
        w3  = Web3(Web3.HTTPProvider(NETWORKS["bnb"]["rpc_url"]))
        if not w3.is_connected():
            return {"success": False, "error": "bnb_rpc_unreachable"}

        account   = w3.eth.account.from_key(privkey)
        nonce     = w3.eth.get_transaction_count(account.address)
        gas_price = w3.eth.gas_price

        USDT_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"
        to_checksum  = Web3.to_checksum_address(to_address)
        amount_wei   = int(amount_usd * 1e18)

        # USDT transfer() signature: 0xa9059cbb
        data = bytes.fromhex("a9059cbb") + bytes.fromhex(to_checksum[2:]) + amount_wei.to_bytes(32, "big")

        tx = {
            "to":       USDT_CONTRACT,
            "value":    0,
            "data":     data.hex(),
            "gas":      70000,
            "gasPrice": gas_price,
            "nonce":    nonce,
            "chainId":  56,
        }
        signed  = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        return {
            "success":      True,
            "tx_hash":      tx_hash.hex(),
            "explorer_url": f"https://bscscan.com/tx/{tx_hash.hex()}",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── Payout Result ──────────────────────────────────────────────────────────
@dataclass
class PayoutResult:
    success:      bool
    amount_usd:   float
    method:       str
    tx_hash:      str
    explorer_url: str
    fee_usd:      float
    error:        str

    def to_dict(self) -> dict:
        return {
            "success":      self.success,
            "amount_usd":   self.amount_usd,
            "method":       self.method,
            "tx_hash":      self.tx_hash or "",
            "explorer_url": self.explorer_url or "",
            "fee_usd":      self.fee_usd,
            "error":        self.error or "",
            "timestamp":    datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        }

# ── Main payout function ──────────────────────────────────────────────────
def pay_to_owner(amount_usd: float, method: str = "bnb") -> PayoutResult:
    """
    Send `amount_usd` to owner's BNB wallet.

    Two modes:
    1. BNB_PRIVATE_KEY set → sends real BNB or USDT on BNB chain automatically
    2. No private key → marks as 'awaiting_funding'; owner can withdraw via
       manual transfer using their own wallet

    Receiving address: always BNB_RECEIVING_ADDRESS from config.yaml
    """
    if amount_usd <= 0:
        return PayoutResult(False, amount_usd, method, "", "", 0, "amount <= 0")

    # ── BNB / USDT ─────────────────────────────────────────────────────────
    if method == "bnb":
        if not BNB_RECEIVING_ADDRESS:
            return PayoutResult(False, amount_usd, "bnb", "", "", 0,
                                "bnb_receiving_address not set in config.yaml")

        net         = NETWORKS["bnb"]
        fee_usd     = _estimate_gas_usd("bnb", net["gas_units"])
        privkey     = _sender_privkey()

        if privkey:
            # Prefer USDT — stable, no price volatility
            result = _usdt_transfer(BNB_RECEIVING_ADDRESS, amount_usd, privkey)
            if result["success"]:
                _add_payout({**result, "amount_usd": amount_usd, "fee_usd": fee_usd, "method": "usdt_bnb"})
                return PayoutResult(True, amount_usd, "usdt_bnb",
                                    result["tx_hash"], result["explorer_url"], fee_usd, "")
            # Fall back to native BNB
            result = _bnb_transfer(BNB_RECEIVING_ADDRESS, amount_usd, privkey)
            if result["success"]:
                _add_payout({**result, "amount_usd": amount_usd, "fee_usd": fee_usd, "method": "bnb"})
                return PayoutResult(True, amount_usd, "bnb",
                                    result["tx_hash"], result["explorer_url"], fee_usd, "")
            return PayoutResult(False, amount_usd, "bnb", "", "", fee_usd, result.get("error", ""))

        # No private key — funds accumulate, owner must withdraw manually
        return PayoutResult(
            False, amount_usd, "bnb", "", "", fee_usd,
            f"awaiting_manual_transfer|add BNB_PRIVATE_KEY in Settings > Advanced "
            f"to auto-transfer.|Your BNB address: {BNB_RECEIVING_ADDRESS}"
        )

    # ── TRON ────────────────────────────────────────────────────────────
    if method == "tron" and os.environ.get("TRON_WALLET_ADDRESS"):
        tron_addr = os.environ["TRON_WALLET_ADDRESS"].strip()
        try:
            import requests
            payload  = {
                "owner_address": tron_addr,
                "to_address":    tron_addr,
                "amount":        int(amount_usd * 1_000_000),
                "visible":       True,
            }
            headers = {"accept": "application/json", "content-type": "application/json"}
            resp = requests.post(
                f"{NETWORKS['tron']['rpc_url']}/wallet/transfer",
                json=payload, headers=headers, timeout=15,
            )
            data = resp.json()
            if "txid" in data:
                _add_payout({**data, "amount_usd": amount_usd, "method": "tron"})
                return PayoutResult(True, amount_usd, "tron", data["txid"],
                                    f"https://tronscan.org/#/transaction/{data['txid']}",
                                    1.0, "")
        except Exception as e:
            return PayoutResult(False, amount_usd, "tron", "", "", 1.0, str(e))

    # ── PayPal ────────────────────────────────────────────────────────────
    if PAYPAL_EMAIL:
        fee = round(amount_usd * 0.02 + 0.25, 2)
        try:
            import requests
            client_id     = os.environ.get("PAYPAL_CLIENT_ID", "")
            client_secret = os.environ.get("PAYPAL_CLIENT_SECRET", "")
            if client_id and client_secret:
                token_resp = requests.post(
                    "https://api-m.paypal.com/v1/oauth2/token",
                    data={"grant_type": "client_credentials"},
                    auth=(client_id, client_secret),
                    headers={"accept": "application/json"}, timeout=10,
                )
                token = token_resp.json().get("access_token")
                if token:
                    payout = {
                        "sender_batch_header": {
                            "sender_batch_id": f"swarm_{int(time.time())}",
                            "email_subject":    "SovereignSwarm Earnings",
                        },
                        "items": [{
                            "recipient_type": "EMAIL",
                            "amount":         {"value": f"{amount_usd - fee:.2f}", "currency": "USD"},
                            "receiver":       PAYPAL_EMAIL,
                            "note":           "SovereignSwarm agent earnings",
                        }]
                    }
                    r = requests.post(
                        "https://api-m.paypal.com/v1/payments/payouts",
                        json=payout,
                        headers={"Authorization": f"Bearer {token}", "content-type": "application/json"},
                        timeout=15,
                    )
                    if r.status_code in (200, 201):
                        batch_id = r.json().get("batch_header", {}).get("payout_batch_id", "")
                        _add_payout({"batch_id": batch_id, "amount_usd": amount_usd, "fee_usd": fee, "method": "paypal"})
                        return PayoutResult(True, amount_usd, "paypal", batch_id, "", fee, "")
        except Exception as e:
            return PayoutResult(False, amount_usd, "paypal", "", "", fee, str(e))

    return PayoutResult(False, amount_usd, method, "", "", 0, "no_payout_method_configured")

# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cfg = _load_config()
    print("═══ SovereignSwarm Crypto Payout Engine ═══")
    print(f"  BNB receiving address : {BNB_RECEIVING_ADDRESS or 'not set'}")
    print(f"  BNB private key       : {'✓ set' if _sender_privkey() else '✗ not set (add in Settings > Advanced)'}")
    print(f"  PayPal email          : {PAYPAL_EMAIL or 'not set'}")
    print()
    print("  To enable auto-payout: Settings > Advanced → Secrets → add BNB_PRIVATE_KEY")
    print("  Funds will be sent to your BNB address automatically when master ≥ $10")
    print()
    r = pay_to_owner(10.0, "bnb")
    print(f"Test payout result: {r.to_dict()}")
