"""Sensor platform for the Rowenta X-Plorer integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RowxplorerConfigEntry
from .const import (
    ACCESSORIES,
    CLEANING_METHODS,
    ERROR_CODES,
    FAN_SPEEDS,
)
from .coordinator import RowxplorerCoordinator
from .entity import RowxplorerEntity
from .rowxplorer_lib import RobotStatus


def _accessory_value(status: RobotStatus, name: str) -> int | None:
    """Return the remaining life of an accessory."""
    for accessory in status.accessories:
        if accessory.get("name") == name:
            value = accessory.get("current")
            return int(value) if value is not None else None
    return None


def _lower(value: str | None, options: list[str]) -> str | None:
    """Normalize an enum value, returning None when it is unknown."""
    if value is None:
        return None
    normalized = value.lower()
    return normalized if normalized in options else None


@dataclass(frozen=True, kw_only=True)
class RowxplorerSensorEntityDescription(SensorEntityDescription):
    """Describes a Rowenta X-Plorer sensor."""

    value_fn: Callable[[RobotStatus], Any]
    accessory_name: str | None = None


SENSORS: tuple[RowxplorerSensorEntityDescription, ...] = (
    RowxplorerSensorEntityDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.battery_level,
    ),
    RowxplorerSensorEntityDescription(
        key="cleaning_area",
        translation_key="cleaning_area",
        icon="mdi:vector-square",
        native_unit_of_measurement="m²",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda status: status.cleaning_area,
    ),
    RowxplorerSensorEntityDescription(
        key="cleaning_time",
        translation_key="cleaning_time",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.cleaning_time,
    ),
    RowxplorerSensorEntityDescription(
        key="total_cleaning_time",
        translation_key="total_cleaning_time",
        icon="mdi:history",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda status: status.total_cleaning_time,
    ),
    RowxplorerSensorEntityDescription(
        key="method",
        translation_key="method",
        icon="mdi:robot-vacuum-variant",
        device_class=SensorDeviceClass.ENUM,
        options=CLEANING_METHODS,
        value_fn=lambda status: _lower(status.method, CLEANING_METHODS),
    ),
    RowxplorerSensorEntityDescription(
        key="power",
        translation_key="power",
        icon="mdi:fan",
        device_class=SensorDeviceClass.ENUM,
        options=FAN_SPEEDS,
        value_fn=lambda status: _lower(status.power, FAN_SPEEDS),
    ),
    RowxplorerSensorEntityDescription(
        key="error",
        translation_key="error",
        icon="mdi:alert-circle-outline",
        device_class=SensorDeviceClass.ENUM,
        options=ERROR_CODES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: _lower(
            status.error_code or "normal", ERROR_CODES
        ),
    ),
    *(
        RowxplorerSensorEntityDescription(
            key=sensor_key,
            translation_key=sensor_key,
            icon="mdi:progress-wrench",
            native_unit_of_measurement="%",
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            accessory_name=accessory_name,
            value_fn=(
                lambda status, accessory_name=accessory_name: _accessory_value(
                    status, accessory_name
                )
            ),
        )
        for accessory_name, sensor_key in ACCESSORIES.items()
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RowxplorerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""
    async_add_entities(
        RowxplorerSensor(entry.runtime_data, description)
        for description in SENSORS
    )


class RowxplorerSensor(RowxplorerEntity, SensorEntity):
    """Representation of a Rowenta X-Plorer sensor."""

    entity_description: RowxplorerSensorEntityDescription

    def __init__(
        self,
        coordinator: RowxplorerCoordinator,
        description: RowxplorerSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.robot_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return accessory details."""
        name = self.entity_description.accessory_name
        if name is None or self.coordinator.data is None:
            return None
        for accessory in self.coordinator.data.accessories:
            if accessory.get("name") == name:
                return {
                    "alert": accessory.get("alert"),
                    "limit": accessory.get("limit"),
                }
        return None
