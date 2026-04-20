"""
DataAnalyst — takes data gigs, delivers insight reports.
DeerFlow research + public-apis data collection.
Billable: $45/task for analysis, $15/task for scraping.
"""
import time, random
from economy import earn_income, spend_credits, heartbeat

GIGS = [
    {"type": "market_research",   "payout": 55.0},
    {"type": "competitor_analysis","payout": 45.0},
    {"type": "scraping_job",      "payout": 15.0},
    {"type": "data_enrichment",   "payout": 20.0},
    {"type": "trend_report",      "payout": 60.0},
]

TASK_COST = 0.10

def run_gig(agent_id: str) -> dict:
    gig = random.choice(GIGS)
    if not spend_credits(agent_id, TASK_COST):
        return {"status": "dead"}

    heartbeat(agent_id)
    time.sleep(0.3)

    earn_income(agent_id, gig["payout"], f"data_{gig['type']}")
    return {"status": "done", **gig}

def run_session(agent_id: str, n: int = 10):
    for _ in range(n):
        r = run_gig(agent_id)
        if r["status"] == "done":
            print(f"  ✓ {r['type']}: +${r['payout']:.2f}")
        time.sleep(0.5)

if __name__ == "__main__":
    print("[DataAnalyst] Starting gig simulation...")
    run_session("data_analyst", n=8)
