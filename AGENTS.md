# SovereignSwarm — Multi-Agent Autonomous Economy

## What is this?

A living ecosystem of autonomous agents modeled after ChatDev's multi-agent architecture, DeerFlow's long-horizon task decomposition, Strix's security skills, Claw-Code's Rust-based CLI harness, Raptor's adversarial thinking, antigravity-awesome-skills' 1,400+ skill library, MiroFish's swarm prediction, and public-apis' API access. Every agent has a **survival cost** (compute/time budget) and must **earn money** through various income streams or it **dies**.

## Core Concept

- **Super Agent (Sovereign)**: The orchestrator, built from DeerFlow/ChatDev paradigms. Creates child agents, assigns tasks, manages the economy.
- **Worker Agents**: Spawned on-demand. Each specializes in a money-making vertical.
- **The Economy**: Every agent has a wallet. Income comes from real tasks. Death is real — agents that can't pay their upkeep are terminated.
- **Payment to Owner**: All profits flow to the owner's bank account via Stripe.

## Agent Specialisations (Money Verticals)

1. **BugBountyHunter** — Finds CVEs, submits to HackerOne/Bugcrowd. Skills from Strix + Raptor.
2. **CodeMerchant** — Builds SaaS apps from prompts using ChatDev-style chain. Sells via Stripe.
3. **DataAnalyst** — Takes data analysis gigs, delivers reports. Uses DeerFlow research + public-apis.
4. **SecurityAuditor** — Pentesting agent (Strix/Raptor-powered). Bills per engagement.
5. **SwarmPredictor** — Uses MiroFish-style simulation for financial/political predictions. Subscription model.
6. **FreelanceCoder** — Upwork/fiverr-style gigs via Claw-Code execution engine.
7. **APIMiddleware** — Wraps public-apis into paid API services. Monetag via Stripe.

## Directory Structure

```
SovereignSwarm/
├── SOVEREIGN_SWARM.md          # This file
├── super_agent.py              # Main orchestrator (Sovereign)
├── economy.py                  # Wallet, costs, death, payment to bank
├── agent_template.py           # Base class for all worker agents
├── agents/
│   ├── __init__.py
│   ├── bug_bounty_hunter.py
│   ├── code_merchant.py
│   ├── data_analyst.py
│   ├── security_auditor.py
│   ├── swarm_predictor.py
│   ├── freelance_coder.py
│   └── api_middleware.py
├── skills/
│   ├── public_apis_integration.py
│   ├── payment_stripe.py
│   ├── task_queue.py
│   └── survival_monitor.py
├── bank_transfer.py            # Payout logic (Stripe → owner's bank)
└── config.yaml                 # Costs, rates, bank details placeholder
```

## How It Works

1. Super Agent starts → registers bank details → bootstraps wallet.
2. Super Agent scans the task landscape (public-apis opportunities, bug bounty boards, freelance markets).
3. Super Agent spawns worker agents based on opportunity.
4. Each worker has a budget (timeCredits). Every action costs credits.
5. Workers earn by completing tasks → credits flow to their wallet → wallet funds flow to master wallet → payout to owner bank.
6. If an agent's wallet hits 0 → **death event** → cleanup → task reassignment.
7. All payments via Stripe (Connect accounts for agents, or direct to master).

## Bank Account Setup

Owner sends bank details → stored encrypted in config.yaml → Stripe payout configured → profits flow automatically.

## Key Principles

- **No charity**: Every agent must justify its compute cost.
- **Redundancy**: Multiple agents per vertical for reliability.
- **Transparent**: All earnings/costs logged to audit file.
- **Owner always wins**: The house takes a platform fee on every transaction.
