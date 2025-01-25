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
BATTERY_PREFIX = 'batt'
ONLINE_PREFIX = 'online'

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
            hw_version=device.get('versionHard', ''),
            sw_version=device.get('versionSoft', ''),
            via_device=(DOMAIN, config['email'])
        )
        _LOGGER.debug(f"Created device_info: {device_info}")
        sensors.extend([
            TemperatureSensor(coordinator, device, device_info, deviceId),
            HumiditySensor(coordinator, device, device_info, deviceId),
            BatterySensor(coordinator, device, device_info, deviceId),
            OnlineSensor(coordinator, device, device_info, deviceId)
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
        
        # Map sensor types to their prefixes
        prefix_map = {
            'temperature': TEMPERATURE_PREFIX,
            'humidity': HUMIDITY_PREFIX,
            'battery': BATTERY_PREFIX,
            'online': ONLINE_PREFIX
        }
        prefix = prefix_map.get(sensor_type, 'unknown')
        self._attr_unique_id = f"{prefix}{idx}"
        self._attr_device_info = device_info

    def _is_data_valid(self) -> bool:
        """Check if the data is valid based on online status and freshness."""
        try:
            device_data = self.coordinator.data[self.idx]['deviceExt']
            last_device_data = device_data['lastDeviceData']
            device_settings = device_data['deviceSettings']
            
            # Check online status
            if not last_device_data['online']:
                return False
                
            # Check data freshness based on uploadRate
            last_time = int(last_device_data['lastTime'])
            now = int(datetime.datetime.now().timestamp() * 1000)  # Convert to milliseconds
            upload_rate = int(device_settings['uploadRate'])
            max_allowed_delay = upload_rate * 60 * 1000 * 1.2  # Convert minutes to milliseconds and add 20%
            
            return (now - last_time) < max_allowed_delay
            
        except (KeyError, ValueError, TypeError):
            return False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.sensor_type == 'online':
            try:
                return self.coordinator.data[self.idx]['deviceExt']['lastDeviceData']['online']
            except (KeyError, ValueError, TypeError):
                return None
        
        if not self._is_data_valid():
            return None
            
        if self.sensor_type in ['temperature', 'humidity']:
            data_key = 'tem' if self.sensor_type == 'temperature' else 'hum'
            return self.coordinator.data[self.idx]['deviceExt']['lastDeviceData'][data_key] / 100
        return None


class TemperatureSensor(GoveeSensor):
    """Temperature sensor for Govee devices."""

    _sensor_option_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:thermometer"
    
    def __init__(self, coordinator, device, device_info, idx):
        """Initialize the temperature sensor."""
        super().__init__(coordinator, device, device_info, idx, 'temperature')


class HumiditySensor(GoveeSensor):
    """Humidity sensor for Govee devices."""
    
    _attr_icon = "mdi:water-percent"
    
    def __init__(self, coordinator, device, device_info, idx):
        """Initialize the humidity sensor."""
        super().__init__(coordinator, device, device_info, idx, 'humidity')


class BatterySensor(GoveeSensor):
    """Battery sensor for Govee devices."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:battery"
    _attr_entity_registry_enabled_default = True
    
    def __init__(self, coordinator, device, device_info, idx):
        """Initialize the battery sensor."""
        super().__init__(coordinator, device, device_info, idx, 'battery')

    @property
    def state(self):
        """Return the state of the sensor."""
        if not self._is_data_valid():
            return None
        return self.coordinator.data[self.idx]['deviceExt']['deviceSettings']['battery']


class OnlineSensor(GoveeSensor):
    """Online status sensor for Govee devices."""
    
    _attr_icon = "mdi:cloud-check"
    _attr_entity_registry_enabled_default = False
    
    def __init__(self, coordinator, device, device_info, idx):
        """Initialize the online sensor."""
        super().__init__(coordinator, device, device_info, idx, 'online')

    @property
    def state(self):
        """Return the state of the sensor."""
        try:
            return self.coordinator.data[self.idx]['deviceExt']['lastDeviceData']['online']
        except (KeyError, ValueError, TypeError):
            return None
