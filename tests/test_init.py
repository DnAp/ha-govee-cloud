"""Tests for setting up Govee Cloud and its entities."""
from __future__ import annotations

import json

import aiohttp
import pytest
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.govee_cloud.api import DEVICES_URL, LOGIN_URL
from custom_components.govee_cloud.const import DOMAIN, ISSUE_APP_VERSION
from custom_components.govee_cloud.coordinator import has_current_readings

from .conftest import EMAIL, LOGIN_APP_VERSION, LOGIN_BAD_PASSWORD, PASSWORD, make_device, mock_govee


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """Sensors carry device classes, units and values."""
    mock_govee(aioclient_mock, [make_device("AA:01", "Bedroom", tem=2150, hum=4512, battery=80)])
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    temperature = hass.states.get("sensor.bedroom_temperature")
    assert temperature.state == "21.5"
    assert temperature.attributes["device_class"] == "temperature"
    assert temperature.attributes["state_class"] == "measurement"
    assert temperature.attributes["unit_of_measurement"] == "°C"
    assert temperature.attributes["friendly_name"] == "Bedroom Temperature"

    humidity = hass.states.get("sensor.bedroom_humidity")
    assert humidity.state == "45.12"
    assert humidity.attributes["device_class"] == "humidity"

    battery = hass.states.get("sensor.bedroom_battery")
    assert battery.state == "80"
    assert battery.attributes["device_class"] == "battery"

    upload_rate = hass.states.get("sensor.bedroom_upload_rate")
    assert upload_rate.state == "10"
    assert upload_rate.attributes["friendly_name"] == "Bedroom Upload Rate"

    registry = er.async_get(hass)
    assert registry.async_get("sensor.bedroom_upload_rate").entity_category == "diagnostic"
    assert registry.async_get("sensor.bedroom_temperature").unique_id == "tempAA:01"
    online = registry.async_get("binary_sensor.bedroom_online")
    assert online.unique_id == "onlineAA:01"
    assert online.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    [device] = dr.async_entries_for_config_entry(dr.async_get(hass), config_entry.entry_id)
    assert device.identifiers == {(DOMAIN, "AA:01")}
    assert device.entry_type is None
    assert device.model == "H5179"
    assert device.via_device_id is None


async def test_offline_device_is_unavailable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """An offline device's readings are not current, even with a recent lastTime.

    Seen in the wild: a low-battery sensor reported online=false with one
    minutes-old reading and then nothing on its next upload slot.
    """
    mock_govee(
        aioclient_mock,
        [make_device("AA:02", "Outdoor", online=False, age_minutes=5, upload_rate=30, battery=6)],
    )
    await _setup(hass, config_entry)

    for entity_id in ("sensor.outdoor_temperature", "sensor.outdoor_humidity", "sensor.outdoor_battery"):
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.outdoor_upload_rate").state == "30"


async def test_stale_data_is_unavailable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """Readings older than the upload interval allows are unavailable."""
    mock_govee(aioclient_mock, [make_device("AA:03", "Attic", age_minutes=60 * 24, upload_rate=30)])
    await _setup(hass, config_entry)

    for entity_id in ("sensor.attic_temperature", "sensor.attic_humidity", "sensor.attic_battery"):
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.attic_upload_rate").state == "30"


async def test_device_filtering(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """Untested thermo-hygrometers are added; lights and broken devices are skipped."""
    light = {
        "device": "LL:01",
        "sku": "H6008",
        "deviceName": "Lamp",
        "deviceExt": {"lastDeviceData": "", "deviceSettings": "{}", "extResources": "not json"},
    }
    mock_govee(
        aioclient_mock,
        [make_device("AA:04", "Kitchen"), make_device("AA:05", "Garage", sku="H5075"), light],
    )
    await _setup(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.kitchen_temperature").state == "21.5"
    assert hass.states.get("sensor.garage_temperature").state == "21.5"
    assert hass.states.get("sensor.lamp_temperature") is None


async def test_reading_missing_values(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """Null readings on a supported model give unknown instead of an exception."""
    mock_govee(aioclient_mock, [make_device("AA:06", "Cellar", tem=None, hum=None, battery=None)])
    await _setup(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.cellar_temperature").state == "unknown"
    assert hass.states.get("sensor.cellar_battery").state == "unknown"


@pytest.mark.parametrize(
    "response",
    [{"exc": aiohttp.ClientError()}, {"exc": TimeoutError()}, {"status": 500, "text": "oops"}],
)
async def test_setup_retries_when_govee_is_down(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    response: dict,
) -> None:
    """A Govee outage at startup leaves the entry retrying instead of dead."""
    aioclient_mock.post(LOGIN_URL, **response)
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_starts_reauth_on_bad_password(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """A rejected password asks the user for a new one."""
    mock_govee(aioclient_mock, [], login=LOGIN_BAD_PASSWORD)
    await _setup(hass, config_entry)

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_app_version_creates_repair_issue(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """An outdated app version is surfaced as a repair issue and cleared later."""
    mock_govee(aioclient_mock, [], login=LOGIN_APP_VERSION)
    await _setup(hass, config_entry)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_APP_VERSION)
    assert issue is not None
    assert issue.translation_placeholders["message"].startswith("The app version is too low")

    mock_govee(aioclient_mock, [make_device("AA:07", "Bedroom")])
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_APP_VERSION) is None


async def test_migration_from_0_1(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Entries and registry data from 0.1.x are upgraded in place."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Govee Cloud ({EMAIL})",
        data={"email": EMAIL, "password": PASSWORD},
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "AA:08")},
        name="Bedroom",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    registry = er.async_get(hass)
    old_temperature = registry.async_get_or_create(
        "sensor", DOMAIN, "tempAA:08", config_entry=entry, suggested_object_id="bedroom_temperature"
    )
    registry.async_get_or_create(
        "sensor", DOMAIN, "onlineAA:08", config_entry=entry, suggested_object_id="bedroom_online"
    )

    mock_govee(aioclient_mock, [make_device("AA:08", "Bedroom")])
    await _setup(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert entry.unique_id == EMAIL.lower()
    assert registry.async_get_entity_id("sensor", DOMAIN, "onlineAA:08") is None
    assert registry.async_get_entity_id("binary_sensor", DOMAIN, "onlineAA:08") is not None
    # Existing entities keep their entity_id.
    assert registry.async_get_entity_id("sensor", DOMAIN, "tempAA:08") == old_temperature.entity_id
    assert hass.states.get(old_temperature.entity_id).state == "21.5"
    assert dr.async_get(hass).async_get(device.id).entry_type is None


async def test_remove_stale_device(
    hass: HomeAssistant,
    hass_ws_client,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """A device gone from the Govee account can be removed; a live one cannot."""
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "config", {})
    mock_govee(aioclient_mock, [make_device("AA:10", "Bedroom")])
    registry = dr.async_get(hass)
    stale = registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, "GONE:01")}, name="Family room"
    )
    await _setup(hass, config_entry)
    [live] = [
        device
        for device in dr.async_entries_for_config_entry(registry, config_entry.entry_id)
        if (DOMAIN, "AA:10") in device.identifiers
    ]

    client = await hass_ws_client(hass)

    async def remove(device_id: str) -> bool:
        await client.send_json_auto_id(
            {
                "type": "config/device_registry/remove_config_entry",
                "config_entry_id": config_entry.entry_id,
                "device_id": device_id,
            }
        )
        return (await client.receive_json())["success"]

    assert await remove(live.id) is False
    assert await remove(stale.id) is True
    remaining = {device.id for device in dr.async_entries_for_config_entry(registry, config_entry.entry_id)}
    assert remaining == {live.id}


async def test_unload(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """The entry unloads cleanly."""
    mock_govee(aioclient_mock, [make_device("AA:09", "Bedroom")])
    await _setup(hass, config_entry)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


def _device(age_minutes: float, upload_rate, online=True) -> dict:
    raw = make_device("X", "X", age_minutes=age_minutes, upload_rate=upload_rate, online=online)
    return {"deviceExt": {key: json.loads(value) for key, value in raw["deviceExt"].items()}}


@pytest.mark.parametrize(
    ("age_minutes", "upload_rate", "current"),
    [
        (14, 10, True),  # 10 min + 5 min floor
        (16, 10, False),
        (35, 30, True),  # 30 min + 20%
        (37, 30, False),
        (5, 1, True),  # 1 min + 5 min floor
        (7, 1, False),
        (14, 0, True),  # bogus rate falls back to the poll interval
        (16, 0, False),
    ],
)
def test_has_current_readings_age(age_minutes: float, upload_rate: int, current: bool) -> None:
    """Readings are current up to the upload interval plus max(20%, 5 minutes)."""
    assert has_current_readings(_device(age_minutes, upload_rate)) is current


@pytest.mark.parametrize("online", [False, None, "true"])
def test_has_current_readings_requires_online(online) -> None:
    """Fresh readings of a device Govee does not report as online are not current."""
    assert has_current_readings(_device(1, 10, online=online)) is False


def test_has_current_readings_without_timestamp() -> None:
    """Without lastTime the readings cannot be trusted."""
    device = {"deviceExt": {"lastDeviceData": {"online": True}, "deviceSettings": {"uploadRate": 10}}}
    assert has_current_readings(device) is False
