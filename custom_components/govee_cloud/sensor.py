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
    DataUpdateCoordinator,
    UpdateFailed,
)

from . import api

SUPPORTED_SKU = ['H5179']
# UPDATE_INTERVAL = datetime.timedelta(minutes=10)
UPDATE_INTERVAL = datetime.timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass: HomeAssistant,
        config: ConfigType,
        async_add_entities: AddEntitiesCallback,
        discovery_info: DiscoveryInfoType | None = None,
) -> None:
    _LOGGER.debug('TEst')

    sensors_in_device = {}
    config['token'] = config.get('token', None)
    async def async_update_data():
        _LOGGER.error('Updating data')
        if config['token'] is None:
            config['token'] = await api.get_access_token(config['email'], config['password'])
        if config['token'] is None:
            raise UpdateFailed("Grovee Cloud: Failed to get access token")
        # devices = await hass.async_add_executor_job(api.get_devices, config['token'])
        devices = await api.get_devices(config['token'])
        if devices is None:
            _LOGGER.warning("Grovee Cloud: Failed to get devices. Update token on next run")
            config['token'] = None
            return
        _LOGGER.warning('Got devices: %s', str(devices))
        for device in devices:
            if device.sku not in SUPPORTED_SKU:
                continue
            if device.device not in sensors:
                sensors_in_device[device.device] = [TemperatureSensor(device), HumiditySensor(device)]
                async_add_entities(sensors_in_device[device.device])
                continue
            for sensor in sensors_in_device[device.device]:
                sensor.update(device)
    async def async_update_data_wrapper():
        _LOGGER.error('Updating data wrapper')
        await hass.async_add_executor_job(async_update_data)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=SENSOR_DOMAIN,
        update_method=async_update_data_wrapper,
        update_interval=UPDATE_INTERVAL,
    )
    _LOGGER.debug('Refreshing data')
    # await coordinator.async_config_entry_first_refresh()

    await coordinator.async_refresh()
    # await async_update_data()


class TemperatureSensor(SensorEntity):
    def __init__(self, device):
        self._state = None
        self._name = device['deviceName'] + ' Temperature'
        self.update(device)

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        return TEMP_CELSIUS

    def update(self, device) -> None:
        self._state = device['deviceExt']['lastDeviceData']['tem']


class HumiditySensor(SensorEntity):
    def __init__(self, device):
        self._state = None
        self._name = device['deviceName'] + ' Temperature'
        self.update(device)

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        return PERCENTAGE

    def update(self, device) -> None:
        self._state = device['deviceExt']['lastDeviceData']['hum']
