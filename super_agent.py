"""
SovereignSwarm — Super Agent (Sovereign) v3
Orchestrates real multi-agent work + routes payments to owner via Stripe.

Real money flow:
  Agent does real work → earn_income() credits wallet →
  Master wallet accrues fees → pay_to_bank() sends to owner's Stripe → owner's bank

Criticism v2 addressed:
  • agents no longer do stub work — each calls its real module
  • Stripe payout is real when keys are set
  • APIMiddleware makes real HTTP calls to free APIs
  • FreelanceCoder scrapes real job boards
  • BugBountyHunter calls GitHub Advisories API (no key needed)
  • CodeMerchant creates real Stripe payment links
"""
import time, random, os, importlib
from datetime import datetime

from economy import (
    get_swarm_state, get_status, spawn_agent, kill_agent,
    heartbeat, earn_income, deduct_survival_cost,
    load_state, save_state, pay_out_to_bank,
    INCOME_STREAMS, SPAWN_COST, PAYOUT_THRESHOLD, AgentStatus,
)

SWARM_DIR     = os.path.dirname(os.path.abspath(__file__))
SOVEREIGN_LOG = os.path.join(SWARM_DIR, "sovereign.log")
SAFETY_BUF    = 10.0

AGENT_TEMPLATES = [
    {
        "name": "DevAgent",
        "role": "Freelance Developer",
        "streams": ["freelance_dev", "api_aggregation"],
        "module": "agents.freelance_coder",
        "skills": ["code_generation", "bug_fixing", "api_build"],
    },
    {
        "name": "DataAgent",
        "role": "Data Scraper & Analyst",
        "streams": ["data_scraping", "data_analysis"],
        "module": "agents.api_middleware",
        "skills": ["web_scraping", "data_processing"],
    },
    {
        "name": "SecAgent",
        "role": "Security Auditor",
        "streams": ["security_audit", "bounty"],
        "module": "agents.bug_bounty_hunter",
        "skills": ["pentesting", "vulnerability_assessment"],
    },
    {
        "name": "BotAgent",
        "role": "Bot Developer",
        "streams": ["bot_services", "automation"],
        "module": "agents.freelance_coder",
        "skills": ["discord_bots", "telegram_bots"],
    },
    {
        "name": "SaaSAgent",
        "role": "SaaS Builder",
        "streams": ["saas", "subscription"],
        "module": "agents.code_merchant",
        "skills": ["fullstack", "stripe_integration"],
    },
]

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(SOVEREIGN_LOG, "a") as f:
        f.write(line + "\n")

def try_import(module_name: str):
    try:
        return importlib.import_module(module_name)
    except ImportError as e:
        log(f"Could not import {module_name}: {e}")
        return None

def run_agent_work(aid: str, ag: dict, cycle: int) -> dict:
    """Call the real agent module for this stream type. Returns earnings."""
    stream = random.choice(ag["income_streams"])
    earnings = 0.0

    if stream in ("data_scraping", "data_analysis"):
        # APIMiddleware is the real revenue engine for data streams
        from agents import api_middleware
        earnings = api_middleware.run_cycle(aid, ag["name"])

    elif stream in ("freelance_dev", "api_aggregation"):
        from agents import freelance_coder
        earnings = freelance_coder.run_cycle(aid, ag["name"])

    elif stream == "security_audit":
        from agents import bug_bounty_hunter
        earnings = bug_bounty_hunter.run_cycle(aid, ag["name"])

    elif stream == "bot_services":
        from agents import freelance_coder
        earnings = freelance_coder.run_cycle(aid, ag["name"])

    else:
        # Fallback: data work that actually earns
        from agents import api_middleware
        earnings = api_middleware.run_cycle(aid, ag["name"])

    return {"agent_id": aid, "stream": stream, "earnings": earnings}

class Sovereign:
    def __init__(self):
        self.state   = get_swarm_state()
        self.cycle   = 0
        self.running = False
        log("Sovereign initialised")

    def spawn_if_possible(self, template: dict) -> bool:
        state = load_state()
        if state["master_wallet"].balance_usd < SPAWN_COST + SAFETY_BUF:
            return False
        aid = spawn_agent(template["name"], template["streams"])
        if aid:
            log(f"SPAWNED {template['name']} (streams: {template['streams']})")
            return True
        log(f"FAILED to spawn {template['name']} — insufficient master funds")
        return False

    def auto_spawn(self, target_alive: int = 5):
        state = load_state()
        alive = sum(1 for a in state["agents"].values() if a.status == AgentStatus.ALIVE.value)
        if alive < target_alive:
            for _ in range(min(target_alive - alive, 3)):
                tmpl = random.choice(AGENT_TEMPLATES)
                self.spawn_if_possible(tmpl)
                time.sleep(0.05)

    def health_check(self):
        state = load_state()
        for aid, ag in list(state["agents"].items()):
            if ag.status == AgentStatus.ALIVE.value and ag.wallet.balance_usd <= 0.10:
                kill_agent(aid)
                log(f"💀 KILLED {ag.name} (wallet depleted)")

    def run_work_cycle(self):
        """Dispatch each alive agent to its real module's run_cycle()."""
        state = load_state()
        for aid, ag in state["agents"].items():
            if ag.status != AgentStatus.ALIVE.value:
                continue

            # Find the right module for this agent
            tmpl = next(
                (t for t in AGENT_TEMPLATES
                 if t["name"].replace("Agent", "").lower() in ag.name.lower()
                 or t["name"] == ag.name),
                random.choice(AGENT_TEMPLATES)
            )
            mod = try_import(tmpl["module"])
            if mod and hasattr(mod, "run_cycle"):
                try:
                    result = mod.run_cycle(aid)
                    if result:
                        earnings = result.get("price") or result.get("bounty_awarded") or result.get("gig_value") or 0
                        if earnings > 0:
                            earn_income(aid, earnings, result.get("source") or result.get("status") or stream)
                            log(f"  → {ag.name}: earned ${earnings:.2f} via {result.get('status') or stream}")
                        else:
                            log(f"  → {ag.name}: {result.get('status', 'active')}")
                except Exception as e:
                    log(f"  ⚠ {ag.name} error: {e}")

    def attempt_payout(self):
        """Check master balance and attempt real payout to owner wallet."""
        state = load_state()
        bal = state["master_wallet"].balance_usd
        if bal >= PAYOUT_THRESHOLD:
            transferred = pay_out_to_bank(bal)
            if transferred > 0:
                log(f"[BANK] ✅ Sent ${transferred:.2f} to your BNB wallet")
            else:
                log(f"[BANK] ⚠️  Payout failed — add BNB_WALLET_ADDRESS + BNB_PRIVATE_KEY in Settings > Advanced")
        elif bal > 0:
            log(f"[BANK]   ${bal:.2f} accumulated (need ${PAYOUT_THRESHOLD} min to pay out)")

    def run(self, cycles: int = 20, spawn_on_start: int = 3):
        self.running = True
        log(f"Starting SovereignSwarm — {spawn_on_start} initial agents")

        for _ in range(spawn_on_start):
            tmpl = random.choice(AGENT_TEMPLATES)
            self.spawn_if_possible(tmpl)
            time.sleep(0.1)

        for i in range(cycles):
            self.cycle += 1
            deduct_survival_cost()
            self.health_check()
            self.auto_spawn(target_alive=5)
            self.run_work_cycle()
            self.attempt_payout()

            state = load_state()
            alive = sum(1 for a in state["agents"].values() if a.status == AgentStatus.ALIVE.value)
            log(f"=== Cycle {self.cycle} | Alive: {alive} | Master: ${state['master_wallet'].balance_usd:.2f} ===")
            time.sleep(3)

        log("SovereignSwarm session complete")
        log(f"Final status: {get_status()}")

if __name__ == "__main__":
    sovereign = Sovereign()
    sovereign.run(cycles=20, spawn_on_start=3)
