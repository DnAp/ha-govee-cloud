"""Support for Govee Cloud sensors."""
from __future__ import annotations

import logging
import datetime

from homeassistant.components.sensor import (
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from . import api
from .const import DOMAIN

TEMPERATURE_PREFIX = 'temp'
HUMIDITY_PREFIX = 'hum'

SUPPORTED_SKU = ['H5179']
UPDATE_INTERVAL = datetime.timedelta(minutes=10)

_LOGGER = logging.getLogger(__name__)


def devices_filter(devices):
    """Filter supported devices."""
    filtered_devices = {}
    for deviceId in devices:
        device = devices[deviceId]
        if device['sku'] not in SUPPORTED_SKU:
            _LOGGER.warning('Not supported devices: %s. Model: ' + device['sku'], device['deviceName'])
            continue
        filtered_devices[deviceId] = device
    return filtered_devices


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Govee Cloud sensor based on a config entry."""
    config = hass.data[DOMAIN][entry.entry_id]

    class GoveeDataHandler:
        def __init__(self):
            self.token = None

        async def get_token(self):
            """Get or refresh the access token."""
            self.token = await api.get_access_token(config['email'], config['password'])
            if self.token is None:
                raise UpdateFailed('Failed to get access token')
            return self.token

    handler = GoveeDataHandler()
    await handler.get_token()

    async def async_update_data():
        """Fetch data from API endpoint."""
        _LOGGER.debug('Updating data')
        devices = await api.get_devices(handler.token)
        if devices is None:
            _LOGGER.warning('Failed to get devices. Token may be expired.')
            await handler.get_token()
            devices = await api.get_devices(handler.token)
            if devices is None:
                raise UpdateFailed('Failed to get devices.')
        return devices_filter(devices)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=UPDATE_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    sensors = []
    for deviceId, device in coordinator.data.items():
        device_info = DeviceInfo(
            name=device['deviceName'],
            identifiers={(DOMAIN, deviceId)},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer='Govee',
            model=device['sku'],
            sw_version=device.get('version', ''),
            via_device=(DOMAIN, config['email'])
        )
        _LOGGER.debug(f"Created device_info: {device_info}")
        sensors.extend([
            TemperatureSensor(coordinator, device, device_info, deviceId),
            HumiditySensor(coordinator, device, device_info, deviceId)
        ])

    async_add_entities(sensors)


class GoveeSensor(CoordinatorEntity, SensorEntity):
    """Base class for Govee sensors."""

    def __init__(self, coordinator, device, device_info, idx, sensor_type):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.idx = idx
        self.sensor_type = sensor_type
        self._name = f"{device['deviceName']} {sensor_type.capitalize()}"
        self._attr_unique_id = f"{TEMPERATURE_PREFIX if sensor_type == 'temperature' else HUMIDITY_PREFIX}{idx}"
        self._attr_device_info = device_info

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        data_key = 'tem' if self.sensor_type == 'temperature' else 'hum'
        return self.coordinator.data[self.idx]['deviceExt']['lastDeviceData'][data_key] / 100


class TemperatureSensor(GoveeSensor):
    """Temperature sensor for Govee devices."""

    _sensor_option_unit_of_measurement = UnitOfTemperature.CELSIUS
    
    def __init__(self, coordinator, device, device_info, idx):
        """Initialize the temperature sensor."""
        super().__init__(coordinator, device, device_info, idx, 'temperature')


class HumiditySensor(GoveeSensor):
    """Humidity sensor for Govee devices."""
    
    def __init__(self, coordinator, device, device_info, idx):
        """Initialize the humidity sensor."""
        super().__init__(coordinator, device, device_info, idx, 'humidity')
