from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_BLUE_KEY, CONF_PASSWORD, CONF_USERNAME, DOMAIN

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD, CONF_BLUE_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    runtime_data = getattr(config_entry, "runtime_data", hass.data[DOMAIN][config_entry.entry_id])

    return {
        "entry": async_redact_data(dict(config_entry.data), TO_REDACT),
        "data": async_redact_data(dict(runtime_data.coordinator.data or {}), TO_REDACT),
    }
