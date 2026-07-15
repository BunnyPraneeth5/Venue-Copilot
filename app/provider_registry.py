from enum import Enum

class ProviderStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    DISABLED = "DISABLED"

class ProviderRegistry:
    def __init__(self) -> None:
        # Default status for each agent is ACTIVE
        self._statuses = {
            "occupancy_agent": ProviderStatus.ACTIVE,
            "fan_mix_agent": ProviderStatus.ACTIVE,
            "flow_agent": ProviderStatus.ACTIVE,
        }

    def get_status(self, provider_name: str) -> ProviderStatus:
        """Returns the current status of the specified provider."""
        return self._statuses.get(provider_name, ProviderStatus.ACTIVE)

    def set_status(self, provider_name: str, status: ProviderStatus) -> None:
        """Sets the status of the specified provider."""
        self._statuses[provider_name] = ProviderStatus(status)

    def reset(self) -> None:
        """Resets all provider statuses to ACTIVE."""
        for key in self._statuses:
            self._statuses[key] = ProviderStatus.ACTIVE

    def get_all_statuses(self) -> dict[str, str]:
        """Returns the dictionary containing statuses of all registered providers."""
        return {k: v.value for k, v in self._statuses.items()}

# Global provider registry instance
provider_registry = ProviderRegistry()
