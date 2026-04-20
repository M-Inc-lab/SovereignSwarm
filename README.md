# SovereignSwarm — README

## What is this?
A living ecosystem of autonomous agents that earn money to survive. Inspired by ChatDev, DeerFlow, Strix, Claw-Code, Raptor, MiroFish, antigravity-awesome-skills, and public-apis.

## Core Concept
- **Sovereign (Super Agent)**: Orchestrator that spawns worker agents, assigns tasks, handles payouts
- **Worker Agents**: Spawned by Sovereign, each has a wallet, survival cost, income streams
- **Death**: If an agent's wallet hits $0, it dies — tasks reassigned
- **Payout**: Master wallet accumulates → auto-transfers to YOUR bank account (Stripe)

## Income Streams
1. **Freelance Dev** — write code for clients via API
2. **Data Scraping** — gather data for businesses
3. **API Aggregation** — build & monetize API wrappers
4. **Security Audits** — pentesting via Strix skills
5. **Content Generation** — articles, copy, code via LLM
6. **Bot Networks** — Discord/Telegram bots for businesses
7. **Data Analysis** — insight reports for companies
8. **Automation-as-a-Service** —替人自动化工作流程

## Setup
```bash
cd /home/workspace/SovereignSwarm
pip install stripe pyyaml httpx
export STRIPE_SECRET_KEY=sk_...
python super_agent.py
```

## Bank Account
Owner will provide Stripe Connect account details for automatic payouts.

## Files
- `super_agent.py` — Sovereign orchestrator
- `economy.py` — Wallet, credit, death, payout logic
- `agent_template.py` — Base worker agent class
- `config.yaml` — Survival costs, fees, income streams
- `income_streams/` — Individual income stream implementations