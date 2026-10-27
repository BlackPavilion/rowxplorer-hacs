"""Base entity for the Rowenta X-Plorer integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RowxplorerCoordinator


class RowxplorerEntity(CoordinatorEntity[RowxplorerCoordinator]):
    """Base class for Rowenta X-Plorer entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: RowxplorerCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.robot_id)},
            manufacturer="Rowenta (Groupe SEB)",
            model=coordinator.model,
            name=coordinator.entry.title,
            serial_number=coordinator.robot_id,
        )
