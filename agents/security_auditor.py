"""
SecurityAuditor — professional pentest engagements.
Strix/Raptor-powered: port scan → vuln assess → report → bill.
Billable per engagement: $75–500/task.
"""
import time, random
from economy import earn_income, spend_credits, heartbeat

ENGAGEMENT_TYPES = [
    {"scope": "web_app",       "payout": 120.0},
    {"scope": "network_scan",  "payout": 200.0},
    {"scope": "api_pentest",   "payout": 180.0},
    {"scope": "full_audit",    "payout": 450.0},
]

PHASES = ["recon", "enum", "exploit", "doc", "report"]
PHASE_COST = 0.20

def run_audit(agent_id: str) -> dict:
    engagement = random.choice(ENGAGEMENT_TYPES)
    total_cost = len(PHASES) * PHASE_COST
    if not spend_credits(agent_id, total_cost):
        return {"status": "dead"}

    report = {"engagement_id": f"audit_{random.randint(1000,9999)}",
              "scope": engagement["scope"],
              "phases": [],
              "payout": engagement["payout"]}

    for phase in PHASES:
        heartbeat(agent_id)
        report["phases"].append(phase)
        time.sleep(0.2)

    earn_income(agent_id, engagement["payout"], f"audit_{engagement['scope']}")
    report["status"] = "completed"
    return report

if __name__ == "__main__":
    print("[SecurityAuditor] Starting audit simulation...")
    for _ in range(5):
        r = run_audit("sec_auditor")
        if r["status"] == "completed":
            print(f"  ✓ {r['engagement_id']} ({r['scope']}): ${r['payout']:.2f}")
        time.sleep(1)
