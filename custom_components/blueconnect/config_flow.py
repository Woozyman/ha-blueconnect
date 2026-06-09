from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .api import BlueConnectApi, BlueConnectApiError, BlueConnectAuthError
from .const import CONF_BLUE_KEY, CONF_PASSWORD, CONF_USERNAME, DEFAULT_NAME, DOMAIN


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


def _schema(defaults: Mapping[str, str] | None = None) -> vol.Schema:
    defaults = defaults or {}

    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): str,
            vol.Required(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): str,
            vol.Required(CONF_BLUE_KEY, default=defaults.get(CONF_BLUE_KEY, "")): str,
        }
    )


async def _validate_input(hass: HomeAssistant, data: dict[str, str]) -> dict[str, str]:
    api = BlueConnectApi(
        hass,
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        data[CONF_BLUE_KEY],
    )

    try:
        await api.async_get_measurement()
    except BlueConnectAuthError as err:
        raise InvalidAuth from err
    except BlueConnectApiError as err:
        raise CannotConnect from err

    return {"title": f"{DEFAULT_NAME} {data[CONF_BLUE_KEY]}"}


class BlueConnectConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Blue Connect."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, str] | None = None) -> FlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_BLUE_KEY])
            self._abort_if_unique_id_configured()

            try:
                info = await _validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pragma: no cover - defensive fallback
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(step_id="user", data_schema=_schema(user_input), errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle reauthentication."""

        return await self.async_step_reauth_confirm(dict(entry_data))

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the reauthentication confirmation step."""

        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        defaults = dict(entry.data)

        if user_input is not None:
            data = {
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_BLUE_KEY: user_input[CONF_BLUE_KEY],
            }

            try:
                await _validate_input(self.hass, data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pragma: no cover - defensive fallback
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(data[CONF_BLUE_KEY])
                self.hass.config_entries.async_update_entry(entry, data=data, title=f"{DEFAULT_NAME} {data[CONF_BLUE_KEY]}")
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_schema(user_input or defaults),
            errors=errors,
        )
