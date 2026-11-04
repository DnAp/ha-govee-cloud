"""Data update coordinator for Govee Cloud."""
from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    APP_VERSION,
    GoveeApi,
    GoveeApiError,
    GoveeAppVersionError,
    GoveeAuthError,
)
from .const import DOMAIN, ISSUE_APP_VERSION, SUPPORTED_SKU, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type GoveeConfigEntry = ConfigEntry[GoveeCoordinator]

# Extra time on top of the device's upload interval before its readings count
# as stale: 20% of the interval, but never less than this.
MIN_STALE_MARGIN_SECONDS = 5 * 60


def has_climate_data(device: dict[str, Any]) -> bool:
    """Return True if the device reports temperature and humidity."""
    last = device["deviceExt"]["lastDeviceData"]
    return all(
        isinstance(last.get(key), (int, float)) and not isinstance(last.get(key), bool)
        for key in ("tem", "hum")
    )


def has_current_readings(device: dict[str, Any], now: float | None = None) -> bool:
    """Return True if Govee reports the device online and its readings are fresh.

    An offline device can still carry a recent `lastTime`, e.g. from a reading
    the phone app synced over Bluetooth, but it no longer reports regularly, so
    its readings are not treated as current.
    """
    ext = device["deviceExt"]
    if ext["lastDeviceData"].get("online") is not True:
        return False
    try:
        last_time = int(ext["lastDeviceData"]["lastTime"]) / 1000
        upload_rate = float(ext["deviceSettings"]["uploadRate"]) * 60
    except (KeyError, TypeError, ValueError):
        return False
    if upload_rate <= 0:
        upload_rate = UPDATE_INTERVAL.total_seconds()
    max_age = upload_rate + max(upload_rate * 0.2, MIN_STALE_MARGIN_SECONDS)
    return (now if now is not None else time.time()) - last_time < max_age


class GoveeCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Polls the Govee cloud for all devices of one account."""

    config_entry: GoveeConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: GoveeConfigEntry, api: GoveeApi
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api
        self._reported_devices: set[str] = set()

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            devices = await self.api.get_devices()
        except GoveeAppVersionError as err:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_APP_VERSION,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key=ISSUE_APP_VERSION,
                translation_placeholders={"version": APP_VERSION, "message": str(err)},
            )
            raise UpdateFailed(f"Govee rejected app version {APP_VERSION}: {err}") from err
        except GoveeAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except GoveeApiError as err:
            raise UpdateFailed(str(err)) from err

        ir.async_delete_issue(self.hass, DOMAIN, ISSUE_APP_VERSION)
        return self._filter_supported(devices)

    def _filter_supported(
        self, devices: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        supported: dict[str, dict[str, Any]] = {}
        for device_id, device in devices.items():
            sku = device.get("sku")
            if sku in SUPPORTED_SKU:
                supported[device_id] = device
                continue
            first_time = device_id not in self._reported_devices
            self._reported_devices.add(device_id)
            if has_climate_data(device):
                if first_time:
                    _LOGGER.info(
                        "Adding %s (model %s): not tested with this integration, "
                        "but it reports temperature and humidity",
                        device.get("deviceName"),
                        sku,
                    )
                supported[device_id] = device
            elif first_time:
                _LOGGER.info(
                    "Skipping %s (model %s): not supported", device.get("deviceName"), sku
                )
        return supported
