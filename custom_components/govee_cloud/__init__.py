"""The Govee Cloud integration."""
from __future__ import annotations

import logging

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GoveeApi
from .const import DOMAIN, ONLINE_PREFIX
from .coordinator import GoveeConfigEntry, GoveeCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: GoveeConfigEntry) -> bool:
    """Set up Govee Cloud from a config entry."""
    api = GoveeApi(
        async_get_clientsession(hass), entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD]
    )
    coordinator = GoveeCoordinator(hass, entry, api)
    # Raises ConfigEntryNotReady (HA retries) or ConfigEntryAuthFailed (reauth).
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GoveeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: GoveeConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow removing a device only once it is gone from the Govee account."""
    devices = entry.runtime_data.data or {}
    return not any(
        domain == DOMAIN and device_id in devices
        for domain, device_id in device_entry.identifiers
    )


async def async_migrate_entry(hass: HomeAssistant, entry: GoveeConfigEntry) -> bool:
    """Migrate config entries created by older versions."""
    if entry.version > 1:
        return False

    if entry.minor_version < 2:
        # 1.1 -> 1.2: entries get the account e-mail as unique_id, and the
        # "online" sensor moved to the binary_sensor platform.
        unique_id = entry.unique_id
        if unique_id is None:
            candidate = entry.data[CONF_EMAIL].strip().lower()
            if not any(
                other.unique_id == candidate
                for other in hass.config_entries.async_entries(DOMAIN)
                if other.entry_id != entry.entry_id
            ):
                unique_id = candidate

        registry = er.async_get(hass)
        for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
            if registry_entry.domain == Platform.SENSOR and registry_entry.unique_id.startswith(
                ONLINE_PREFIX
            ):
                registry.async_remove(registry_entry.entity_id)

        hass.config_entries.async_update_entry(
            entry, unique_id=unique_id, version=1, minor_version=2
        )
        _LOGGER.debug("Migrated config entry %s to version 1.2", entry.entry_id)

    return True
