"""Config flow for Govee Cloud."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GoveeApi, GoveeAppVersionError, GoveeAuthError, GoveeConnectionError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class GoveeCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Govee Cloud."""

    VERSION = 1
    MINOR_VERSION = 2

    async def _async_try_login(self, email: str, password: str) -> dict[str, str]:
        """Try the credentials; return form errors, empty on success."""
        api = GoveeApi(async_get_clientsession(self.hass), email, password)
        try:
            await api.login()
        except GoveeAuthError:
            return {"base": "invalid_auth"}
        except GoveeAppVersionError:
            return {"base": "app_version"}
        except GoveeConnectionError:
            return {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error while logging in to Govee")
            return {"base": "unknown"}
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()

            errors = await self._async_try_login(email, user_input[CONF_PASSWORD])
            if not errors:
                return self.async_create_entry(
                    title=f"Govee Cloud ({email})",
                    data={CONF_EMAIL: email, CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, {CONF_EMAIL: (user_input or {}).get(CONF_EMAIL)}
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication after Govee rejected the stored password."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new password."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_try_login(
                entry.data[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors,
        )
