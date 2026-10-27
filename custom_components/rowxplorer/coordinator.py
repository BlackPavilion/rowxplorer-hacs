"""Coordinator for the Rowenta X-Plorer integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import timedelta
from functools import partial
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_MQTT_ENDPOINT,
    CONF_PRODUCT_ID,
    CONF_REFRESH_TOKEN,
    CONF_ROBOT_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PRODUCT_MODELS,
)
from .rowxplorer_lib import (
    AuthenticationError,
    RobotStatus,
    RowxplorerClient,
    SebAuth,
    SebAuthConfig,
    SebMqttConfig,
)

_LOGGER = logging.getLogger(__name__)


class RowxplorerCoordinator(DataUpdateCoordinator[RobotStatus]):
    """Poll the SEB cloud for the robot status and send commands."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.robot_id: str = entry.data[CONF_ROBOT_ID]
        self.product_id: str = entry.data[CONF_PRODUCT_ID]
        self._command_lock = asyncio.Lock()

        self.auth = SebAuth(
            SebAuthConfig(refresh_token=entry.data[CONF_REFRESH_TOKEN])
        )
        self.client = RowxplorerClient.seb(
            auth=self.auth,
            mqtt_config=SebMqttConfig(
                mqtt_endpoint=entry.data[CONF_MQTT_ENDPOINT],
                product_id=self.product_id,
                robot_id=self.robot_id,
                client_id=f"#homeassistant-{entry.entry_id[:8]}",
                timeout=20.0,
            ),
        )
        # The robot publishes its status on the MQTT ``status`` topic. Use
        # those messages for near-real-time updates; the periodic poll stays
        # as a fallback (and to refresh the connection).
        self.client.transport.status_callback = self._on_status_push

        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    @property
    def model(self) -> str:
        """Return a human readable model name."""
        return PRODUCT_MODELS.get(self.product_id, self.product_id)

    def _on_status_push(self, payload: dict[str, Any]) -> None:
        """Handle a status message pushed by the robot (MQTT thread)."""
        self.hass.loop.call_soon_threadsafe(self._async_handle_status_push, payload)

    @callback
    def _async_handle_status_push(self, payload: dict[str, Any]) -> None:
        """Apply a pushed status payload to the coordinator data."""
        try:
            status = RobotStatus.from_dict(payload)
        except Exception:  # noqa: BLE001 - payload comes from the cloud
            _LOGGER.debug("Ignoring unparsable pushed status: %s", payload)
            return
        _LOGGER.debug(
            "Pushed status for %s: %s (battery %s)",
            self.robot_id,
            status.execution_state,
            status.battery_level,
        )
        self.async_set_updated_data(status)

    async def _async_update_data(self) -> RobotStatus:
        """Fetch the current robot status."""
        async with self._command_lock:
            try:
                return await self.hass.async_add_executor_job(self.client.status)
            except AuthenticationError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except Exception as err:  # noqa: BLE001 - transport boundary
                # Force a clean reconnect on the next poll: a half-open
                # WebSocket would otherwise keep failing forever.
                await self.hass.async_add_executor_job(
                    self.client.transport.disconnect
                )
                raise UpdateFailed(
                    f"Error communicating with the robot: {err}"
                ) from err

    async def async_run_command(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """Run a blocking robot command in the executor."""
        async with self._command_lock:
            try:
                result = await self.hass.async_add_executor_job(
                    partial(func, *args, **kwargs)
                )
            except AuthenticationError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except Exception as err:  # noqa: BLE001 - transport boundary
                await self.hass.async_add_executor_job(
                    self.client.transport.disconnect
                )
                raise HomeAssistantError(
                    f"Error sending command to the robot: {err}"
                ) from err
        await self.async_request_refresh()
        return result

    async def async_shutdown(self) -> None:
        """Close the MQTT connection when the entry is unloaded."""
        self.client.transport.status_callback = None
        await super().async_shutdown()
        await self.hass.async_add_executor_job(self.client.transport.disconnect)
