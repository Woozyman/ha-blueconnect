from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BlueConnectRuntimeData
from .coordinator import BlueConnectDataUpdateCoordinator
from .sensor import BlueConnectEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Blue Connect refresh button from a config entry."""

    runtime_data: BlueConnectRuntimeData = entry.runtime_data
    async_add_entities(
        [BlueConnectRefreshButton(runtime_data.coordinator, runtime_data.api.blue_key)]
    )


class BlueConnectRefreshButton(BlueConnectEntity, ButtonEntity):
    """Button to manually refresh Blue Connect data when allowed."""

    _attr_translation_key = "refresh"

    def __init__(self, coordinator: BlueConnectDataUpdateCoordinator, blue_key: str) -> None:
        super().__init__(coordinator, blue_key)
        self._attr_unique_id = f"{blue_key}_refresh"

    @property
    def available(self) -> bool:
        """Only allow pressing when the API cooldown has elapsed."""

        return super().available and self.coordinator.call_allowed

    async def async_press(self) -> None:
        """Request a fresh measurement from the API."""

        await self.coordinator.async_request_refresh()
