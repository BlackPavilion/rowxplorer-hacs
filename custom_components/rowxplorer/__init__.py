"""Rowenta X-Plorer integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .coordinator import RowxplorerCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.VACUUM]

type RowxplorerConfigEntry = ConfigEntry[RowxplorerCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: RowxplorerConfigEntry) -> bool:
    """Set up Rowenta X-Plorer from a config entry."""
    coordinator = RowxplorerCoordinator(hass, entry)
    # Use async_refresh() instead of async_config_entry_first_refresh() so that
    # an offline robot does not tear down the coordinator (and its cached
    # SebAuth tokens/Cognito credentials) in an 80-second ConfigEntryNotReady
    # loop. Entities load as unavailable and the coordinator backs off cleanly.
    await coordinator.async_refresh()
    if isinstance(coordinator.last_exception, ConfigEntryAuthFailed):
        await coordinator.async_shutdown()
        raise coordinator.last_exception

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RowxplorerConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    ):
        coordinator = entry.runtime_data
        await coordinator.async_shutdown()
    return unload_ok
