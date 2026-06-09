from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricPotential, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import BlueConnectRuntimeData
from .const import DEFAULT_NAME, DOMAIN
from .coordinator import BlueConnectDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class BlueConnectSensorEntityDescription(SensorEntityDescription):
    """Blue Connect sensor entity description."""

    value_fn: Callable[[Mapping[str, Any]], Any]


SENSOR_DESCRIPTIONS: tuple[BlueConnectSensorEntityDescription, ...] = (
    BlueConnectSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("temperature_celsius"),
    ),
    BlueConnectSensorEntityDescription(
        key="ph",
        translation_key="ph",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("ph"),
    ),
    BlueConnectSensorEntityDescription(
        key="orp",
        translation_key="orp",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("orp_mV"),
    ),
    BlueConnectSensorEntityDescription(
        key="salinity",
        translation_key="salinity",
        native_unit_of_measurement="g/L",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("salinity_g_per_l"),
    ),
    BlueConnectSensorEntityDescription(
        key="last_measurement",
        translation_key="last_measurement",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: _parse_timestamp(data.get("timestamp")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Blue Connect sensor entities from a config entry."""

    runtime_data: BlueConnectRuntimeData = entry.runtime_data
    coordinator = runtime_data.coordinator

    async_add_entities(
        [
            BlueConnectSensor(coordinator, runtime_data.api.blue_key, description)
            for description in SENSOR_DESCRIPTIONS
        ]
        + [BlueConnectStatusSensor(coordinator, runtime_data.api.blue_key)]
    )


class BlueConnectEntity(CoordinatorEntity[BlueConnectDataUpdateCoordinator]):
    """Base entity for Blue Connect."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BlueConnectDataUpdateCoordinator, blue_key: str) -> None:
        super().__init__(coordinator)
        self._blue_key = blue_key

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for Blue Connect."""

        return DeviceInfo(
            identifiers={(DOMAIN, self._blue_key)},
            manufacturer="Riiot Labs",
            model=DEFAULT_NAME,
            name=DEFAULT_NAME,
        )


class BlueConnectSensor(BlueConnectEntity, SensorEntity):
    """Representation of a Blue Connect sensor."""

    entity_description: BlueConnectSensorEntityDescription

    def __init__(
        self,
        coordinator: BlueConnectDataUpdateCoordinator,
        blue_key: str,
        description: BlueConnectSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, blue_key)
        self.entity_description = description
        self._attr_unique_id = f"{blue_key}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""

        return self.entity_description.value_fn(self.coordinator.data)


class BlueConnectStatusSensor(BlueConnectEntity, SensorEntity):
    """Representation of the Blue Connect status sensor."""

    _attr_translation_key = "status"

    def __init__(self, coordinator: BlueConnectDataUpdateCoordinator, blue_key: str) -> None:
        super().__init__(coordinator, blue_key)
        self._attr_unique_id = f"{blue_key}_status"

    @property
    def native_value(self) -> str | None:
        """Return the derived overall status."""

        statuses = self.extra_state_attributes["status"]
        if not statuses:
            return None

        first_problem = next((status for status in statuses if not status.endswith("_OK") and status != "OK"), None)
        return first_problem or "OK"

    @property
    def extra_state_attributes(self) -> dict[str, list[str]]:
        """Return the raw status list as attributes."""

        statuses = self.coordinator.data.get("status")
        if not isinstance(statuses, list):
            statuses = []
        return {"status": [str(status) for status in statuses]}


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse the Blue Connect timestamp value."""

    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        parsed = dt_util.parse_datetime(value)
        if parsed is not None:
            return parsed

    return None
