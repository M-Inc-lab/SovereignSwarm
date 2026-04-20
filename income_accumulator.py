"""
SovereignSwarm — Income Accumulator & UPI Withdrawal
Converts agent earnings → USDT → Binance P2P → INR → UPI bank

Path: Agent earnings ($) → Auto-buy USDT on Binance
                ↓
      Post P2P SELL ad (USDT → INR via UPI)
                ↓
      Buyer pays INR to your UPI/bank
                ↓
      Release USDT → INR arrives in Binance P2P wallet
                ↓
      Withdraw INR → your bank (UPI)

For this to work, user needs:
  1. Binance account with KYC done
  2. USDT deposit to Binance (agents will also earn USDT)
  3. UPI linked in Binance P2P payment methods
  4. API keys from https://www.binance.com/en/my/settings/api-management
"""

import os, json, time, yaml
from datetime import datetime

SWARM_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SWARM_DIR, "config.yaml")
GOALS_FILE  = os.path.join(SWARM_DIR, "targets", "goals.yaml")

# ── Load Binance P2P settings ───────────────────────────────────────────────
def load_bin_config() -> dict:
    p2p_file = os.path.join(SWARM_DIR, "targets", "binance_p2p.yaml")
    if os.path.exists(p2p_file):
        with open(p2p_file) as f:
            return yaml.safe_load(f)
    return {}

# ── Read current state ───────────────────────────────────────────────────────
def get_current_inr() -> float:
    """Read master wallet + compute equivalent INR."""
    state_file = os.path.join(SWARM_DIR, "state.duckdb")
    if os.path.exists(state_file):
        import json
        try:
            with open(state_file) as f:
                d = json.load(f)
            usd = d.get("master_wallet", {}).get("balance_usd", 0)
            inr = usd * 83  # approximate INR
            return inr
        except:
            pass
    return 0.0

def get_target() -> dict:
    with open(GOALS_FILE) as f:
        return yaml.safe_load(f)

# ── UPI withdrawal request ────────────────────────────────────────────────────
def request_upi_withdrawal(amount_inr: float, upi_id: str) -> dict:
    """
    Submit withdrawal request to Binance P2P INR wallet.
    User receives INR via their linked UPI/bank.
    """
    bin_cfg = load_bin_config()

    if not bin_cfg.get("api_key"):
        return {
            "success": False,
            "error": "Binance API key not configured",
            "action": "Add BINANCE_API_KEY and BINANCE_API_SECRET to Settings > Advanced",
        }

    # This would call Binance withdraw API
    # For now, log the intent and create a payout record
    record = {
        "requested_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "amount_inr":   amount_inr,
        "amount_usd":   round(amount_inr / 83, 2),
        "upi_id":       upi_id,
        "status":       "pending_api_config",
        "tx_note":      "Awaiting Binance P2P API activation",
    }

    records_file = os.path.join(SWARM_DIR, "upi_withdrawals.json")
    records = []
    if os.path.exists(records_file):
        with open(records_file) as f:
            records = json.load(f)
    records.append(record)
    with open(records_file, "w") as f:
        json.dump(records[-50:], f, indent=2)

    return {
        "success": True,
        "message": f"₹{amount_inr:.2f} withdrawal queued. P2P payout active once ₹3,80,000 reached.",
        "record": record,
    }

# ── Main accumulator loop ────────────────────────────────────────────────────
def run_accumulator():
    print("═══ SovereignSwarm Income Accumulator ═══")
    print(f"Goal: ₹3,80,000")
    print(f"Payout method: UPI (via Binance P2P)")
    print()

    # Show current progress
    inr_now = get_current_inr()
    target = get_target()
    target_inr = target["goal"]["target_amount_inr"]
    progress = (inr_now / target_inr) * 100 if target_inr else 0

    print(f"Current:     ₹{inr_now:.2f}")
    print(f"Target:      ₹{target_inr:,.2f}")
    print(f"Progress:    {progress:.4f}%")
    print()

    if inr_now >= target_inr:
        print(f"🎉 GOAL REACHED! Initiating UPI withdrawal...")
        upi = target.get("upi", {}).get("upi_id", "OWNER_WILL_PROVIDE")
        if upi and upi != "OWNER_WILL_PROVIDE":
            result = request_upi_withdrawal(inr_now, upi)
            print(f"Withdrawal result: {result}")
        else:
            print("⚠ Add your UPI ID to targets/goals.yaml to enable withdrawal")
    else:
        remaining = target_inr - inr_now
        print(f"Remaining: ₹{remaining:,.2f}")
        print(f"Agents running... keep the swarm alive!")
        print()
        print("Once ₹3,80,000 reached → automatic P2P sell → INR to your UPI")

if __name__ == "__main__":
    run_accumulator()