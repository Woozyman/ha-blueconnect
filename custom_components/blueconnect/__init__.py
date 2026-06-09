from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import BlueConnectApi
from .const import CONF_BLUE_KEY, CONF_PASSWORD, CONF_USERNAME, DOMAIN, PLATFORMS
from .coordinator import BlueConnectDataUpdateCoordinator


@dataclass(slots=True)
class BlueConnectRuntimeData:
    """Runtime data for the Blue Connect integration."""

    api: BlueConnectApi
    coordinator: BlueConnectDataUpdateCoordinator


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Blue Connect integration."""

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Blue Connect from a config entry."""

    api = BlueConnectApi(
        hass,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_BLUE_KEY],
    )
    coordinator = BlueConnectDataUpdateCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    runtime_data = BlueConnectRuntimeData(api=api, coordinator=coordinator)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime_data
    entry.runtime_data = runtime_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload a config entry."""

    await hass.config_entries.async_reload(entry.entry_id)
