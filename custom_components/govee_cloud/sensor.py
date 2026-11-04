"""Sensors for Govee Cloud."""
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
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import BATTERY_PREFIX, HUMIDITY_PREFIX, TEMPERATURE_PREFIX, UPLOAD_RATE_PREFIX
from .coordinator import GoveeConfigEntry, GoveeCoordinator
from .entity import GoveeEntity


def _number(value: Any, scale: float = 1) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value / scale if scale != 1 else value


@dataclass(frozen=True, kw_only=True)
class GoveeSensorEntityDescription(SensorEntityDescription):
    """Describes a Govee sensor."""

    unique_id_prefix: str
    value_fn: Callable[[dict[str, Any], dict[str, Any]], StateType]
    # Unavailable while Govee reports the device offline or its readings are stale.
    requires_current_readings: bool = True


SENSORS: tuple[GoveeSensorEntityDescription, ...] = (
    GoveeSensorEntityDescription(
        key="temperature",
        unique_id_prefix=TEMPERATURE_PREFIX,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda last, settings: _number(last.get("tem"), 100),
    ),
    GoveeSensorEntityDescription(
        key="humidity",
        unique_id_prefix=HUMIDITY_PREFIX,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_fn=lambda last, settings: _number(last.get("hum"), 100),
    ),
    GoveeSensorEntityDescription(
        key="battery",
        unique_id_prefix=BATTERY_PREFIX,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda last, settings: _number(settings.get("battery")),
    ),
    GoveeSensorEntityDescription(
        key="upload_rate",
        translation_key="upload_rate",
        unique_id_prefix=UPLOAD_RATE_PREFIX,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:clock-outline",
        requires_current_readings=False,
        value_fn=lambda last, settings: _number(settings.get("uploadRate")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoveeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Govee Cloud sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        GoveeSensor(coordinator, device_id, description)
        for device_id in coordinator.data
        for description in SENSORS
    )


class GoveeSensor(GoveeEntity, SensorEntity):
    """A Govee sensor."""

    entity_description: GoveeSensorEntityDescription

    def __init__(
        self,
        coordinator: GoveeCoordinator,
        device_id: str,
        description: GoveeSensorEntityDescription,
    ) -> None:
        super().__init__(
            coordinator,
            device_id,
            description,
            description.unique_id_prefix,
            description.requires_current_readings,
        )

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(
            self.last_device_data, self.device_settings
        )
