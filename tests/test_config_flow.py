"""Tests for the Govee Cloud config flow."""
from __future__ import annotations

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.govee_cloud.api import LOGIN_URL
from custom_components.govee_cloud.const import DOMAIN

from .conftest import EMAIL, LOGIN_APP_VERSION, LOGIN_BAD_PASSWORD, LOGIN_OK, PASSWORD, mock_govee


async def _start(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_user_flow(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """A valid login creates an entry keyed by the lower-cased e-mail."""
    mock_govee(aioclient_mock, [])
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"email": f" {EMAIL} ", "password": PASSWORD}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Govee Cloud ({EMAIL})"
    assert result["data"] == {"email": EMAIL, "password": PASSWORD}
    assert result["result"].unique_id == EMAIL.lower()


@pytest.mark.parametrize(
    ("response", "error"),
    [
        ({"json": LOGIN_BAD_PASSWORD}, "invalid_auth"),
        ({"json": LOGIN_APP_VERSION}, "app_version"),
        ({"status": 503, "text": "down"}, "cannot_connect"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, response: dict, error: str
) -> None:
    """Errors are shown on the form and the user can retry."""
    aioclient_mock.post(LOGIN_URL, **response)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"email": EMAIL, "password": PASSWORD}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_govee(aioclient_mock, [])
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"email": EMAIL, "password": PASSWORD}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """The same account cannot be added twice, whatever the e-mail's case."""
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"email": EMAIL.upper(), "password": PASSWORD}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert not aioclient_mock.mock_calls


async def test_reauth_flow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """Reauth stores the new password after a successful login."""
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    aioclient_mock.post(LOGIN_URL, json=LOGIN_BAD_PASSWORD)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"password": "still-wrong"}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    mock_govee(aioclient_mock, [])
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"password": "new-secret"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data["password"] == "new-secret"
