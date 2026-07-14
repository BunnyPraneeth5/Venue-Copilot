from datetime import datetime, timedelta
from contextvars import ContextVar

# ContextVar to store request-scoped simulated minutes offset.
# Using ContextVar makes the clock thread-safe and task-safe for async request concurrency.
_sim_minutes: ContextVar[int] = ContextVar("sim_minutes", default=0)

class SimulatedClock:
    def __init__(self, kickoff_time_str: str = "2026-06-15T18:00:00"):
        self.kickoff_time = datetime.fromisoformat(kickoff_time_str)

    def set_offset(self, minutes: int):
        """Sets the simulated offset in minutes for the current context."""
        _sim_minutes.set(minutes)

    def get_offset(self) -> int:
        """Gets the simulated offset in minutes for the current context."""
        return _sim_minutes.get()

    def now(self) -> datetime:
        """Returns the simulated current time representing kickoff + offset."""
        return self.kickoff_time + timedelta(minutes=_sim_minutes.get())

# Global clock instance to be imported and used by the agents
clock = SimulatedClock()
