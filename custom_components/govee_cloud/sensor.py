from __future__ import annotations

import logging
import datetime

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorEntity,
)
from homeassistant.const import TEMP_CELSIUS, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from . import api

SUPPORTED_SKU = ['H5179']
UPDATE_INTERVAL = datetime.timedelta(minutes=10)

_LOGGER = logging.getLogger(__name__)


def devices_filter(devices):
    filtered_devices = {}
    for deviceId in devices:
        device = devices[deviceId]
        if device['sku'] not in SUPPORTED_SKU:
            continue
        filtered_devices[deviceId] = device
    return filtered_devices


async def async_setup_platform(
        hass: HomeAssistant,
        config: ConfigType,
        async_add_entities: AddEntitiesCallback,
        discovery_info: DiscoveryInfoType | None = None,
) -> None:
    config['token'] = await api.get_access_token(config['email'], config['password'])
    if config['token'] is None:
        _LOGGER.error('Failed to get access token. Check your email and password.')
        return

    async def async_update_data():
        _LOGGER.debug('Updating data')
        devices = await api.get_devices(config['token'])
        if devices is None:
            _LOGGER.warning('Failed to get devices. Token may be expired.')
            config['token'] = await api.get_access_token(config['email'], config['password'])
            devices = await api.get_devices(config['token'])
            if devices is None:
                UpdateFailed('Failed to get devices.')
        return devices_filter(devices)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=SENSOR_DOMAIN,
        update_method=async_update_data,
        update_interval=UPDATE_INTERVAL,
    )
    await coordinator.async_refresh()

    sensors = []
    for deviceId in coordinator.data:
        sensors.append(TemperatureSensor(coordinator, coordinator.data[deviceId], deviceId))
        sensors.append(HumiditySensor(coordinator, coordinator.data[deviceId], deviceId))

    async_add_entities(sensors)


class TemperatureSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, device, idx):
        super().__init__(coordinator)
        self.idx = idx
        self._name = device['deviceName'] + ' Temperature'

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self):
        return self.coordinator.data[self.idx]['deviceExt']['lastDeviceData']['tem'] / 100

    @property
    def unit_of_measurement(self) -> str:
        return TEMP_CELSIUS


class HumiditySensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, device, idx):
        super().__init__(coordinator)
        self.idx = idx
        self._name = device['deviceName'] + ' Humidity'

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self):
        return self.coordinator.data[self.idx]['deviceExt']['lastDeviceData']['hum'] / 100

    @property
    def unit_of_measurement(self) -> str:
        return PERCENTAGE
