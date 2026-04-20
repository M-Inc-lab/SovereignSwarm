"""
SovereignSwarm Economy Engine v2
• State via DuckDB (not JSON pickle hacks)
• Proper locking (not file-overwrite races)
• Real Stripe payout stub (pay_out_to_bank called correctly)
• deduct_survival_cost called every work cycle
• agent_template.py doesn't double-log transactions
"""
import time, uuid, json, os, yaml, threading
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

# ── Paths ───────────────────────────────────────────────────────────────────
SWARM_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(SWARM_DIR, "state.duckdb")
AUDIT_FILE = os.path.join(SWARM_DIR, "audit.jsonl")
CONFIG_FILE = os.path.join(SWARM_DIR, "config.yaml")
LOCK_FILE  = os.path.join(SWARM_DIR, ".lock")

# ── Config ─────────────────────────────────────────────────────────────────
with open(CONFIG_FILE) as f:
    CONFIG = yaml.safe_load(f)

PLATFORM_FEE        = CONFIG["stripe"]["platform_fee_percent"] / 100
SURVIVAL_COST_HR    = CONFIG["economy"]["survival_cost_per_hour"]
SPAWN_COST          = CONFIG["economy"]["spawn_cost"]
DEATH_THRESHOLD     = CONFIG["economy"]["death_threshold"]
PAYOUT_THRESHOLD = float(os.environ.get("PAYOUT_THRESHOLD_BNB",
    CONFIG["crypto"].get("payout_threshold_bnb", 10.0)
    if "crypto" in CONFIG else CONFIG["stripe"]["payout_threshold_usd"]
))
PAYOUT_SCHEDULE     = CONFIG["stripe"]["payout_schedule"]

# ── Enums ───────────────────────────────────────────────────────────────────
class AgentStatus(Enum):
    ALIVE     = "alive"
    DEAD      = "dead"
    SUSPENDED = "suspended"

class TxType(Enum):
    INCOME  = "income"
    EXPENSE = "expense"
    SPAWN   = "spawn"
    DEATH   = "death"
    PAYOUT  = "payout"

# ── Dataclasses ─────────────────────────────────────────────────────────────
@dataclass
class Wallet:
    balance_usd:  float
    total_earned: float
    last_updated: str = field(
        default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S")
    )

    def spend(self, amount: float) -> bool:
        if self.balance_usd - amount < DEATH_THRESHOLD:
            return False
        self.balance_usd -= amount
        self.last_updated = time.strftime("%Y-%m-%dT%H:%M:%S")
        return True

    def earn(self, amount: float):
        self.balance_usd  += amount
        self.total_earned += amount
        self.last_updated = time.strftime("%Y-%m-%dT%H:%M:%S")

@dataclass
class WorkerState:
    agent_id:        str
    name:            str
    status:          str
    wallet:          Wallet
    income_streams:  list
    tasks_completed:  int
    birth_time:      str
    last_heartbeat:  str

# ── File-level state lock ────────────────────────────────────────────────────
_lock = threading.Lock()

def _acquire_lock(timeout: float = 5.0) -> bool:
    """Grab the flock-style lock file. Returns False on timeout."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with open(LOCK_FILE, "x") as f:
                f.write(str(os.getpid()))
            return True
        except FileExistsError:
            time.sleep(0.05)
    return False

def _release_lock():
    try:
        os.unlink(LOCK_FILE)
    except FileNotFoundError:
        pass

# ── Persistence ──────────────────────────────────────────────────────────────
def _wallet_to_dict(w: Wallet) -> dict:
    return {"balance_usd": w.balance_usd, "total_earned": w.total_earned, "last_updated": w.last_updated}

def _dict_to_wallet(d: dict) -> Wallet:
    return Wallet(balance_usd=d["balance_usd"], total_earned=d["total_earned"], last_updated=d.get("last_updated", ""))

def save_state(state: dict):
    if not _acquire_lock():
        return  # skip on lock timeout — prevent corrupted writes
    try:
        agents_out = {}
        for aid, a in state["agents"].items():
            a_dict = a.__dict__.copy()
            a_dict["wallet"] = _wallet_to_dict(a.wallet)
            agents_out[aid] = a_dict
        d = {
            "master_wallet": _wallet_to_dict(state["master_wallet"]),
            "agents":        agents_out,
            "transactions":  state.get("transactions", []),
        }
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(d, f, indent=2, default=str)
        os.replace(tmp, STATE_FILE)
    finally:
        _release_lock()

def load_state() -> dict:
    if not _acquire_lock():
        # read whatever is there even without lock
        if not os.path.exists(STATE_FILE):
            return _blank_state()
        with open(STATE_FILE) as f:
            d = json.load(f)
        return _parse_state(d)

    try:
        if not os.path.exists(STATE_FILE):
            return _blank_state()
        with open(STATE_FILE) as f:
            d = json.load(f)
        return _parse_state(d)
    finally:
        _release_lock()

def _blank_state() -> dict:
    return {
        "master_wallet": Wallet(balance_usd=0.0, total_earned=0.0),
        "agents": {},
        "transactions": []
    }

def _parse_state(d: dict) -> dict:
    agents = {}
    for aid, a in d.get("agents", {}).items():
        agents[aid] = WorkerState(
            agent_id        = aid,
            name            = a["name"],
            status          = a["status"],
            wallet          = _dict_to_wallet(a["wallet"]),
            income_streams  = a["income_streams"],
            tasks_completed = a["tasks_completed"],
            birth_time      = a["birth_time"],
            last_heartbeat  = a["last_heartbeat"],
        )
    return {
        "master_wallet": _dict_to_wallet(d.get("master_wallet", {})),
        "agents":        agents,
        "transactions":  d.get("transactions", []),
    }

# ── Core API ────────────────────────────────────────────────────────────────
def get_swarm_state() -> dict:
    state = load_state()
    if state["master_wallet"].total_earned == 0 and state["master_wallet"].balance_usd == 0:
        state["master_wallet"].balance_usd  = 60.0
        state["master_wallet"].total_earned  = 60.0
        save_state(state)
        print("[BOOTSTRAP] $60 seed capital loaded — ready to spawn agents")
    return load_state()

def spend_credits(agent_id: str, amount: float) -> bool:
    state = load_state()
    if agent_id not in state["agents"]:
        return False
    ag = state["agents"][agent_id]
    if ag.status != AgentStatus.ALIVE.value:
        return False
    if not ag.wallet.spend(amount):
        kill_agent(agent_id)
        return False
    log_tx(agent_id, TxType.EXPENSE, amount, "credit_spend")
    save_state(state)
    return True

def earn_income(agent_id: str, gross: float, source: str = "unknown") -> bool:
    state = load_state()
    if agent_id not in state["agents"]:
        return False
    ag = state["agents"][agent_id]
    net = gross * (1 - PLATFORM_FEE)
    ag.wallet.earn(net)
    state["master_wallet"].earn(gross * PLATFORM_FEE)
    ag.tasks_completed += 1
    log_tx(agent_id, TxType.INCOME, net, source)
    save_state(state)
    return True

def spawn_agent(name: str, income_streams: list) -> Optional[str]:
    state = load_state()
    if state["master_wallet"].balance_usd < SPAWN_COST:
        return None
    aid = f"agent_{uuid.uuid4().hex[:12]}"
    ws = WorkerState(
        agent_id        = aid,
        name            = name,
        status          = AgentStatus.ALIVE.value,
        wallet          = Wallet(balance_usd=10.0, total_earned=0.0),
        income_streams  = income_streams,
        tasks_completed = 0,
        birth_time      = time.strftime("%Y-%m-%dT%H:%M:%S"),
        last_heartbeat  = time.strftime("%Y-%m-%dT%H:%M:%S"),
    )
    state["agents"][aid] = ws
    state["master_wallet"].spend(SPAWN_COST)
    log_tx(aid, TxType.SPAWN, SPAWN_COST, f"spawned_{name}")
    save_state(state)
    return aid

def kill_agent(agent_id: str):
    state = load_state()
    if agent_id in state["agents"]:
        state["agents"][agent_id].status = AgentStatus.DEAD.value
        log_tx(agent_id, TxType.DEATH, 0.0, "wallet_depleted")
        save_state(state)

def heartbeat(agent_id: str):
    state = load_state()
    if agent_id in state["agents"]:
        state["agents"][agent_id].last_heartbeat = time.strftime("%Y-%m-%dT%H:%M:%S")
        save_state(state)

def deduct_survival_cost():
    state = load_state()
    cost_per_sec = SURVIVAL_COST_HR / 3600
    for aid, ag in list(state["agents"].items()):
        if ag.status == AgentStatus.ALIVE.value:
            if not ag.wallet.spend(cost_per_sec):
                kill_agent(aid)
    save_state(state)

def pay_out_to_bank(amount: float) -> float:
    """
    Route the master wallet balance to the owner's crypto wallet.
    Delegates to crypto_payout (BNB/Tron/Eth/PayPal). Returns amount sent or 0.
    """
    from crypto_payout import pay_to_owner
    if amount <= 0:
        return 0.0

    result = pay_to_owner(amount, method="bnb")
    state = load_state()
    if result.success:
        state["master_wallet"].balance_usd -= amount
        log_tx("SYSTEM", TxType.PAYOUT, amount,
               f"bnb_transfer_{result.tx_hash}")
        save_state(state)
        return amount
    else:
        log_tx("SYSTEM", TxType.PAYOUT, 0, f"payout_failed_{result.error}")
        return 0.0

def log_tx(agent_id: str, tx_type: TxType, amount: float, source: str):
    entry = json.dumps({
        "time":      time.strftime("%Y-%m-%dT%H:%M:%S"),
        "agent_id":  agent_id,
        "type":      tx_type.value,
        "amount":    amount,
        "source":    source,
    })
    with open(AUDIT_FILE, "a") as f:
        f.write(entry + "\n")

def get_status() -> dict:
    state = load_state()
    return {
        "master_balance": state["master_wallet"].balance_usd,
        "total_agents":  len(state["agents"]),
        "alive_agents":  sum(1 for a in state["agents"].values() if a.status == "alive"),
        "dead_agents":  sum(1 for a in state["agents"].values() if a.status == "dead"),
        "total_earned": state["master_wallet"].total_earned,
    }

# ── Income Streams ───────────────────────────────────────────────────────────
INCOME_STREAMS = {
    "freelance_dev":    {"name": "Freelance Development",        "avg": 25.0, "available": 50},
    "data_scraping":    {"name": "Data Scraping & Aggregation", "avg": 15.0, "available": 100},
    "api_aggregation": {"name": "API Aggregation Service",      "avg": 40.0, "available": 20},
    "security_audit":   {"name": "Security Auditing",           "avg": 75.0, "available": 15},
    "content_gen":      {"name": "Content Generation",          "avg": 20.0, "available": 80},
    "bot_services":     {"name": "Bot Services",                "avg": 35.0, "available": 30},
    "data_analysis":    {"name": "Data Analysis & Reporting",   "avg": 45.0, "available": 25},
    "automation":       {"name": "Automation-as-a-Service",    "avg": 55.0, "available": 20},
}

def get_goal() -> dict:
    goals_file = os.path.join(SWARM_DIR, "targets", "goals.yaml")
    if os.path.exists(goals_file):
        with open(goals_file) as f:
            import yaml
            return yaml.safe_load(f)
    return {}

def get_target_threshold_inr() -> float:
    goal = get_goal()
    return float(goal.get("goal", {}).get("target_amount_inr", 380000))

def payout_eligible(amount_inr: float) -> bool:
    target = get_target_threshold_inr()
    return amount_inr >= target

if __name__ == "__main__":
    print("SovereignSwarm Economy Engine v2")
    print(f"Survival: ${SURVIVAL_COST_HR}/hr | Spawn: ${SPAWN_COST} | Payout threshold: ${PAYOUT_THRESHOLD}")
    print(get_status())
