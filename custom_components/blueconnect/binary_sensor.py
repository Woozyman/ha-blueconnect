from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BlueConnectRuntimeData
from .coordinator import BlueConnectDataUpdateCoordinator
from .sensor import BlueConnectEntity


@dataclass(frozen=True, kw_only=True)
class BlueConnectBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Blue Connect binary sensor entity description."""

    status_key: str


BINARY_SENSOR_DESCRIPTIONS: tuple[BlueConnectBinarySensorEntityDescription, ...] = (
    BlueConnectBinarySensorEntityDescription(
        key="ph_ok",
        translation_key="ph_ok",
        status_key="PH_OK",
    ),
    BlueConnectBinarySensorEntityDescription(
        key="orp_ok",
        translation_key="orp_ok",
        status_key="ORP_OK",
    ),
    BlueConnectBinarySensorEntityDescription(
        key="temperature_ok",
        translation_key="temperature_ok",
        status_key="TEMPERATURE_OK",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Blue Connect binary sensors from a config entry."""

    runtime_data: BlueConnectRuntimeData = entry.runtime_data
    coordinator = runtime_data.coordinator

    async_add_entities(
        [
            BlueConnectBinarySensor(coordinator, runtime_data.api.blue_key, description)
            for description in BINARY_SENSOR_DESCRIPTIONS
        ]
    )


class BlueConnectBinarySensor(BlueConnectEntity, BinarySensorEntity):
    """Representation of a Blue Connect binary sensor."""

    entity_description: BlueConnectBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: BlueConnectDataUpdateCoordinator,
        blue_key: str,
        description: BlueConnectBinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, blue_key)
        self.entity_description = description
        self._attr_unique_id = f"{blue_key}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return whether the measured status is present."""

        statuses = self.coordinator.data.get("status")
        if not isinstance(statuses, list):
            return False

        return self.entity_description.status_key in {str(status) for status in statuses}
