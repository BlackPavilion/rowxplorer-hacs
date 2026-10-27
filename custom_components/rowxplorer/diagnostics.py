"""Diagnostics support for the Rowenta X-Plorer integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import RowxplorerConfigEntry
from .const import CONF_REFRESH_TOKEN

TO_REDACT = {CONF_REFRESH_TOKEN, CONF_USERNAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RowxplorerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    status = entry.runtime_data.data
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "status": status.raw if status is not None else None,
    }
