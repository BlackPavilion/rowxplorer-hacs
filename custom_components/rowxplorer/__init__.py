"""Rowenta X-Plorer integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import RowxplorerCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.VACUUM]

type RowxplorerConfigEntry = ConfigEntry[RowxplorerCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: RowxplorerConfigEntry) -> bool:
    """Set up Rowenta X-Plorer from a config entry."""
    coordinator = RowxplorerCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

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
