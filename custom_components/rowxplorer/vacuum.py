"""Vacuum platform for the Rowenta X-Plorer integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RowxplorerConfigEntry
from .const import (
    FAN_SPEED_NORMAL,
    FAN_SPEEDS,
    STATUS_TO_ACTIVITY,
)
from .coordinator import RowxplorerCoordinator
from .entity import RowxplorerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RowxplorerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the vacuum entity."""
    async_add_entities([RowxplorerVacuum(entry.runtime_data)])


class RowxplorerVacuum(RowxplorerEntity, StateVacuumEntity):
    """Representation of a Rowenta X-Plorer robot vacuum."""

    _attr_name = None
    _attr_supported_features = (
        VacuumEntityFeature.STATE
        | VacuumEntityFeature.START
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.LOCATE
        | VacuumEntityFeature.CLEAN_SPOT
        | VacuumEntityFeature.FAN_SPEED
    )
    _attr_fan_speed_list = [
        FAN_SPEED.capitalize() for FAN_SPEED in FAN_SPEEDS
    ]

    def __init__(self, coordinator: RowxplorerCoordinator) -> None:
        """Initialize the vacuum entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.robot_id}_vacuum"
        self._selected_fan_speed: str | None = None

    @property
    def activity(self) -> VacuumActivity | None:
        """Return the current activity."""
        status = self.coordinator.data
        if status is None:
            return None
        state = (status.execution_state or "").upper()
        return STATUS_TO_ACTIVITY.get(state)

    @property
    def fan_speed(self) -> str | None:
        """Return the current suction power.

        The robot only reports the power while it is running, so fall back to
        the last speed selected from Home Assistant and then to ``Normal``.
        """
        status = self.coordinator.data
        if status is None:
            return None
        power = (
            status.power or self._selected_fan_speed or FAN_SPEED_NORMAL
        ).lower()
        return power.capitalize() if power in FAN_SPEEDS else None

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set the suction power."""
        speed = fan_speed.lower()
        await self.coordinator.async_run_command(
            self.coordinator.client.set_power, speed.upper()
        )
        self._selected_fan_speed = speed

    def _power(self) -> str:
        """Return the power to use for a new cleaning job."""
        status = self.coordinator.data
        power = (
            self._selected_fan_speed
            or (status.power if status else None)
            or FAN_SPEED_NORMAL
        )
        return power.upper()

    async def async_start(self) -> None:
        """Start a full cleaning job."""
        await self.coordinator.async_run_command(
            self.coordinator.client.transport.clean_all,
            power=self._power(),
        )

    async def async_pause(self) -> None:
        """Pause the current cleaning job."""
        await self.coordinator.async_run_command(self.coordinator.client.stop)

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the current cleaning job."""
        await self.coordinator.async_run_command(self.coordinator.client.abort)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Send the robot back to its dock."""
        await self.coordinator.async_run_command(self.coordinator.client.go_home)

    async def async_locate(self, **kwargs: Any) -> None:
        """Make the robot beep."""
        await self.coordinator.async_run_command(self.coordinator.client.localize)

    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Start a spot cleaning job."""
        await self.coordinator.async_run_command(
            self.coordinator.client.transport.clean_spot,
            power=self._power(),
        )
