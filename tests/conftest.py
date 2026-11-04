"""Fixtures for Govee Cloud tests."""
from __future__ import annotations

import json
import time
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.govee_cloud.api import DEVICES_URL, LOGIN_URL
from custom_components.govee_cloud.const import DOMAIN

EMAIL = "User@Example.com"
PASSWORD = "secret"

LOGIN_OK = {"status": 200, "message": "Login successful", "client": {"token": "token-1"}}
LOGIN_BAD_PASSWORD = {"status": 454, "message": ""}
LOGIN_APP_VERSION = {
    "status": 400,
    "message": "The app version is too low, please upgrade the version!",
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: Any) -> None:
    """Allow loading custom_components in every test."""


def make_device(
    device_id: str,
    name: str,
    *,
    sku: str = "H5179",
    online: bool = True,
    age_minutes: float = 2,
    upload_rate: int = 10,
    tem: Any = 2150,
    hum: Any = 4500,
    battery: Any = 80,
    ext: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a device as the Govee device list returns it."""
    last = {
        "online": online,
        "tem": tem,
        "hum": hum,
        "lastTime": int((time.time() - age_minutes * 60) * 1000),
    }
    settings = {"uploadRate": upload_rate, "battery": battery, "deviceName": name}
    device_ext = {
        "lastDeviceData": json.dumps(last),
        "deviceSettings": json.dumps(settings),
        "extResources": json.dumps({"skuUrl": ""}),
    }
    device_ext.update(ext or {})
    return {
        "device": device_id,
        "sku": sku,
        "deviceName": name,
        "versionHard": "1.00.02",
        "versionSoft": "1.03.05",
        "deviceExt": device_ext,
    }


def mock_govee(
    aioclient_mock: AiohttpClientMocker,
    devices: list[dict[str, Any]],
    *,
    login: dict[str, Any] | None = None,
) -> None:
    """Answer Govee's login and device list with the given data."""
    aioclient_mock.clear_requests()
    aioclient_mock.post(LOGIN_URL, json=login or LOGIN_OK)
    aioclient_mock.post(DEVICES_URL, json={"status": 200, "message": "", "devices": devices})


@pytest.fixture
def config_entry(hass: Any) -> MockConfigEntry:
    """A current-version config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Govee Cloud ({EMAIL})",
        data={"email": EMAIL, "password": PASSWORD},
        unique_id=EMAIL.lower(),
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    return entry
