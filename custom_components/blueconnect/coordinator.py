from __future__ import annotations

from datetime import timedelta
from typing import Any
import logging

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BlueConnectApi, BlueConnectApiError, BlueConnectAuthError
from .const import DEFAULT_NAME, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class BlueConnectDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch Blue Connect data."""

    def __init__(self, hass, api: BlueConnectApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DEFAULT_NAME,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Blue Connect API."""

        try:
            return await self.api.async_get_measurement()
        except BlueConnectAuthError as err:
            raise ConfigEntryAuthFailed from err
        except BlueConnectApiError as err:
            raise UpdateFailed(str(err) or "Unable to fetch Blue Connect data") from err
