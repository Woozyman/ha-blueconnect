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

# The RiiotLabs API rejects calls made less than ~45 minutes apart, so we keep
# a matching cooldown after every call (successful or not) to stay within bounds.
MIN_CALL_SPACING = timedelta(minutes=45)


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

    @property
    def next_update(self) -> datetime | None:
        """Return the earliest time a new API call is allowed, if known."""

        return self._suspended_until

    @property
    def call_allowed(self) -> bool:
        """Return whether the API may be called right now."""

        return self._suspended_until is None or dt_util.utcnow() >= self._suspended_until

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Blue Connect API, honouring any active cooldown."""

        now = dt_util.utcnow()

        # If we are still within a cooldown window, do not call the API again.
        # This protects the fragile endpoint from being hammered by manual
        # refreshes, reloads or restarts.
        if self._suspended_until is not None and now < self._suspended_until:
            if self.data is not None:
                remaining = int((self._suspended_until - now).total_seconds())
                _LOGGER.debug(
                    "Skipping Blue Connect update; cooldown active for %s more seconds",
                    remaining,
                )
                return self.data
            return {}

        try:
            data = await self.api.async_get_measurement()
        except BlueConnectAuthError as err:
            raise ConfigEntryAuthFailed from err
        except BlueConnectRateLimitError as err:
            delay = timedelta(seconds=max(err.retry_after, 0)) + RATE_LIMIT_BUFFER
            self._schedule_next(delay)
            minutes = max(1, int(delay.total_seconds() // 60))
            _LOGGER.warning(
                "Blue Connect API rate limit reached; next attempt in about %s minutes",
                minutes,
            )
            # Keep the last known values (or empty data before the first
            # success) instead of failing, so entities stay usable.
            return self.data if self.data else {}
        except BlueConnectApiError as err:
            raise UpdateFailed(str(err) or "Unable to fetch Blue Connect data") from err

        # A successful call also counts against the API's minimum spacing, so
        # schedule the next poll for as soon as another call is permitted. This
        # keeps the countdown and the actual refresh aligned.
        self._schedule_next(MIN_CALL_SPACING + RATE_LIMIT_BUFFER)
        return data

    def _schedule_next(self, delay: timedelta) -> None:
        """Start a cooldown and align the next automatic poll with its end."""

        self._suspended_until = dt_util.utcnow() + delay
        self.update_interval = delay
