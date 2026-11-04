"""Tests for the Govee cloud client."""
from __future__ import annotations

import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from custom_components.govee_cloud.api import (
    DEVICES_URL,
    LOGIN_URL,
    GoveeApi,
    GoveeAppVersionError,
    GoveeAuthError,
    GoveeConnectionError,
    parse_devices,
)

from .conftest import EMAIL, LOGIN_APP_VERSION, LOGIN_BAD_PASSWORD, LOGIN_OK, PASSWORD, make_device


def _api(hass: HomeAssistant) -> GoveeApi:
    return GoveeApi(async_get_clientsession(hass), EMAIL, PASSWORD)


def test_parse_devices_tolerates_malformed_devices() -> None:
    """One broken device must not take the others down."""
    good = make_device("AA", "Good")
    broken = {"device": "BB", "sku": "H6008", "deviceExt": {"lastDeviceData": "", "extResources": "{oops"}}
    parsed = parse_devices([good, broken, "junk", {"sku": "no id"}])

    assert set(parsed) == {"AA", "BB"}
    assert parsed["AA"]["deviceExt"]["lastDeviceData"]["tem"] == 2150
    assert parsed["BB"]["deviceExt"] == {"lastDeviceData": {}, "deviceSettings": {}, "extResources": {}}
    assert parse_devices(None) == {}


@pytest.mark.parametrize(
    ("response", "error"),
    [
        ({"json": LOGIN_APP_VERSION}, GoveeAppVersionError),
        ({"json": LOGIN_BAD_PASSWORD}, GoveeAuthError),
        ({"json": {"status": 500, "message": "busy"}}, GoveeConnectionError),
        ({"status": 502, "text": "<html>Bad gateway</html>"}, GoveeConnectionError),
        ({"text": "<html>maintenance</html>"}, GoveeConnectionError),
        ({"exc": aiohttp.ClientError("boom")}, GoveeConnectionError),
        ({"exc": TimeoutError()}, GoveeConnectionError),
    ],
)
async def test_login_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, response: dict, error: type
) -> None:
    """Login failures are classified so setup knows whether to retry or reauth."""
    aioclient_mock.post(LOGIN_URL, **response)
    with pytest.raises(error):
        await _api(hass).login()


async def test_get_devices_logs_in_again_on_expired_token(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A 401 from the device list triggers one new login."""
    answers = [
        {"status": 401, "message": "please login"},
        {"status": 200, "message": "", "devices": [make_device("AA", "Bedroom")]},
    ]

    async def device_list(method, url, data):
        return AiohttpClientMockResponse(method, url, json=answers.pop(0))

    aioclient_mock.post(LOGIN_URL, json=LOGIN_OK)
    aioclient_mock.post(DEVICES_URL, side_effect=device_list)

    devices = await _api(hass).get_devices()

    assert list(devices) == ["AA"]
    assert sum(1 for call in aioclient_mock.mock_calls if str(call[1]) == LOGIN_URL) == 2


async def test_get_devices_gives_up_when_fresh_token_rejected(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Do not loop forever if Govee rejects even a new token."""
    aioclient_mock.post(LOGIN_URL, json=LOGIN_OK)
    aioclient_mock.post(DEVICES_URL, json={"status": 401, "message": "please login"})

    with pytest.raises(GoveeConnectionError):
        await _api(hass).get_devices()


async def test_get_devices_app_version(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An app version rejection on the device list is reported as such."""
    aioclient_mock.post(LOGIN_URL, json=LOGIN_OK)
    aioclient_mock.post(DEVICES_URL, json=LOGIN_APP_VERSION)

    with pytest.raises(GoveeAppVersionError):
        await _api(hass).get_devices()
