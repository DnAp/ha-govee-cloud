"""Binary sensors for Govee Cloud."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ONLINE_PREFIX
from .coordinator import GoveeConfigEntry, GoveeCoordinator
from .entity import GoveeEntity

ONLINE = BinarySensorEntityDescription(
    key="online",
    translation_key="online",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoveeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Govee Cloud binary sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        GoveeOnlineSensor(coordinator, device_id) for device_id in coordinator.data
    )


class GoveeOnlineSensor(GoveeEntity, BinarySensorEntity):
    """Whether Govee considers the device connected to its cloud."""

    def __init__(self, coordinator: GoveeCoordinator, device_id: str) -> None:
        super().__init__(
            coordinator, device_id, ONLINE, ONLINE_PREFIX, requires_current_readings=False
        )

    @property
    def is_on(self) -> bool | None:
        """Return the cloud's online flag."""
        online = self.last_device_data.get("online")
        return online if isinstance(online, bool) else None
