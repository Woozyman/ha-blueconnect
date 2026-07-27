from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
import logging

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    BlueConnectApi,
    BlueConnectApiError,
    BlueConnectAuthError,
    BlueConnectRateLimitError,
)
from .const import DEFAULT_NAME, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Small safety margin added on top of the cooldown reported by the API.
RATE_LIMIT_BUFFER = timedelta(minutes=1)


class BlueConnectDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch Blue Connect data while respecting rate limits."""

    def __init__(self, hass, api: BlueConnectApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DEFAULT_NAME,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.api = api
        self._suspended_until: datetime | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Blue Connect API, honouring any active cooldown."""

        now = dt_util.utcnow()

        # If the API previously told us to wait, do not call it again until the
        # cooldown has elapsed. This protects the fragile endpoint from being
        # hammered by manual refreshes, reloads or restarts.
        if self._suspended_until is not None and now < self._suspended_until:
            if self.data is not None:
                remaining = int((self._suspended_until - now).total_seconds())
                _LOGGER.debug(
                    "Skipping Blue Connect update; rate limit active for %s more seconds",
                    remaining,
                )
                return self.data
            return {}

        try:
            data = await self.api.async_get_measurement()
        except BlueConnectAuthError as err:
            raise ConfigEntryAuthFailed from err
        except BlueConnectRateLimitError as err:
            self._suspend(err.retry_after)
            minutes = max(1, err.retry_after // 60)
            _LOGGER.warning(
                "Blue Connect API rate limit reached; retrying in about %s minutes",
                minutes,
            )
            # Keep the last known values (or empty data before the first
            # success) instead of failing, so entities stay usable.
            return self.data if self.data else {}
        except BlueConnectApiError as err:
            raise UpdateFailed(str(err) or "Unable to fetch Blue Connect data") from err

        # A successful call clears any active cooldown and restores the cadence.
        self._suspended_until = None
        if self.update_interval != timedelta(seconds=SCAN_INTERVAL):
            self.update_interval = timedelta(seconds=SCAN_INTERVAL)
        return data

    def _suspend(self, retry_after: int) -> None:
        """Record an API-imposed cooldown and defer the next refresh."""

        delay = timedelta(seconds=max(retry_after, 0)) + RATE_LIMIT_BUFFER
        self._suspended_until = dt_util.utcnow() + delay
        # Never poll sooner than both the reported cooldown and the base cadence.
        self.update_interval = max(delay, timedelta(seconds=SCAN_INTERVAL))
