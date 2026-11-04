"""Minimal client for the Govee Home app cloud API."""
from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

LOGIN_URL = "https://app2.govee.com/account/rest/account/v1/login"
DEVICES_URL = "https://app2.govee.com/device/rest/devices/v1/list"

# Govee only issues tokens to a client ID it already knows: a freshly generated
# one is answered with status 454 and no token. Keep this value as is.
CLIENT_ID = "b529ce1f1bd14ff29120b697bd308aa5"
# Govee rejects logins from app versions it considers outdated. When that
# happens again, bump this to the current Govee Home app version.
APP_VERSION = "5.6.01"

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class GoveeApiError(Exception):
    """Base error for the Govee cloud API."""


class GoveeConnectionError(GoveeApiError):
    """Govee could not be reached or answered with something unexpected."""


class GoveeAuthError(GoveeApiError):
    """Govee rejected the credentials."""


class GoveeAppVersionError(GoveeApiError):
    """Govee rejected the app version this integration identifies itself with."""


def _loads(value: Any) -> dict[str, Any]:
    """Decode one of the JSON-in-a-string fields of deviceExt, tolerating junk."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def parse_devices(raw_devices: Any) -> dict[str, dict[str, Any]]:
    """Turn the raw device list into {device_id: device} with decoded deviceExt.

    A malformed device is decoded as far as possible instead of failing the
    whole update for every other device on the account.
    """
    devices: dict[str, dict[str, Any]] = {}
    if not isinstance(raw_devices, list):
        return devices
    for raw in raw_devices:
        if not isinstance(raw, dict) or not raw.get("device"):
            continue
        ext = raw.get("deviceExt")
        if not isinstance(ext, dict):
            ext = {}
        devices[raw["device"]] = {
            **raw,
            "deviceExt": {
                key: _loads(ext.get(key))
                for key in ("lastDeviceData", "deviceSettings", "extResources")
            },
        }
    return devices


class GoveeApi:
    """Talks to the Govee cloud on behalf of one account."""

    def __init__(
        self, session: aiohttp.ClientSession, email: str, password: str
    ) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._token: str | None = None

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Appversion": APP_VERSION,
            "clientId": CLIENT_ID,
            "clientType": "1",
            "iotVersion": "0",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _post(self, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            async with self._session.post(
                url, headers=self._headers(), json=payload, timeout=REQUEST_TIMEOUT
            ) as response:
                if response.status == 429 or response.status >= 500:
                    raise GoveeConnectionError(f"Govee answered HTTP {response.status}")
                try:
                    data = await response.json(content_type=None)
                except ValueError as err:
                    raise GoveeConnectionError(
                        f"Govee sent a non-JSON response (HTTP {response.status})"
                    ) from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise GoveeConnectionError(
                f"Cannot reach Govee: {err or type(err).__name__}"
            ) from err
        if not isinstance(data, dict):
            raise GoveeConnectionError("Govee sent an unexpected response")
        return data

    @staticmethod
    def _raise_for_app_version(data: dict[str, Any]) -> None:
        message = str(data.get("message") or "")
        if "version" in message.lower():
            raise GoveeAppVersionError(message)

    async def login(self) -> None:
        """Log in and keep the token for later requests."""
        self._token = None
        data = await self._post(
            LOGIN_URL,
            {"email": self._email, "client": CLIENT_ID, "password": self._password},
        )
        client = data.get("client")
        token = client.get("token") if isinstance(client, dict) else None
        if token:
            self._token = token
            return

        self._raise_for_app_version(data)
        status = data.get("status")
        message = str(data.get("message") or "").strip() or "no message"
        if isinstance(status, int) and 400 <= status < 500 and status != 429:
            raise GoveeAuthError(f"Govee rejected the login (status {status}: {message})")
        raise GoveeConnectionError(f"Govee login failed (status {status}: {message})")

    async def _fetch_devices(self) -> list[Any] | None:
        """Return the raw device list, or None when Govee wants a new login."""
        data = await self._post(DEVICES_URL)
        if isinstance(data.get("devices"), list):
            return data["devices"]
        self._raise_for_app_version(data)
        if data.get("status") == 401:
            return None
        raise GoveeConnectionError(
            f"Govee did not return devices (status {data.get('status')}: "
            f"{data.get('message') or 'no message'})"
        )

    async def get_devices(self) -> dict[str, dict[str, Any]]:
        """Return all devices on the account, logging in again if needed."""
        if self._token is None:
            await self.login()
        raw = await self._fetch_devices()
        if raw is None:
            _LOGGER.debug("Govee token expired, logging in again")
            await self.login()
            raw = await self._fetch_devices()
            if raw is None:
                raise GoveeConnectionError("Govee keeps rejecting a fresh token")
        return parse_devices(raw)
