"""
SovereignSwarm — Agent Template v2
Passive data class. Work is orchestrated by super_agent.py.
economy.py is the single source of truth for wallet state.
"""
import time, os
from dataclasses import dataclass
from typing import Optional

from economy import heartbeat as eco_heartbeat, load_state

SWARM_DIR = os.path.dirname(os.path.abspath(__file__))

@dataclass
class WorkerAgent:
    """
    Lightweight agent record — reads state from economy.py on demand.
    Does NOT own wallet state (economy.py does that).
    """
    agent_id:       str
    name:           str
    income_streams: list

    @property
    def wallet_usd(self) -> float:
        state = load_state()
        return state["agents"].get(self.agent_id, None) and \
               state["agents"][self.agent_id].wallet.balance_usd

    @property
    def status(self) -> str:
        state = load_state()
        return state["agents"].get(self.agent_id, None) and \
               state["agents"][self.agent_id].status or "unknown"

    @property
    def tasks_completed(self) -> int:
        state = load_state()
        return state["agents"].get(self.agent_id, None) and \
               state["agents"][self.agent_id].tasks_completed or 0

    def send_heartbeat(self):
        eco_heartbeat(self.agent_id)

    def is_alive(self) -> bool:
        return self.status == "alive"
