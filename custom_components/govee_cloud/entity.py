"""Base entity for Govee Cloud."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GoveeCoordinator, has_current_readings


class GoveeEntity(CoordinatorEntity[GoveeCoordinator]):
    """An entity bound to one Govee device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GoveeCoordinator,
        device_id: str,
        description: EntityDescription,
        unique_id_prefix: str,
        requires_current_readings: bool,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = device_id
        self._requires_current_readings = requires_current_readings
        self._attr_unique_id = f"{unique_id_prefix}{device_id}"
        device = coordinator.data[device_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device.get("deviceName"),
            manufacturer="Govee",
            model=device.get("sku"),
            hw_version=device.get("versionHard") or None,
            sw_version=device.get("versionSoft") or None,
            # Clears the "service" type that versions before 0.2.0 registered.
            entry_type=None,
        )

    @property
    def device(self) -> dict[str, Any] | None:
        """Return the latest data of this device, if Govee still lists it."""
        return self.coordinator.data.get(self._device_id)

    @property
    def last_device_data(self) -> dict[str, Any]:
        """Return the device's latest readings."""
        return self.device["deviceExt"]["lastDeviceData"] if self.device else {}

    @property
    def device_settings(self) -> dict[str, Any]:
        """Return the device's settings."""
        return self.device["deviceExt"]["deviceSettings"] if self.device else {}

    @property
    def available(self) -> bool:
        """Return True if there is a device and, if needed, current readings for it."""
        if not super().available or self.device is None:
            return False
        return not self._requires_current_readings or has_current_readings(self.device)
