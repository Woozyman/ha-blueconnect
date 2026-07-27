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
            self._suspend(timedelta(seconds=max(err.retry_after, 0)) + RATE_LIMIT_BUFFER, extend_interval=True)
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

        # A successful call still counts against the API's minimum spacing, so
        # start a fresh cooldown while restoring the normal polling cadence.
        self._suspend(MIN_CALL_SPACING, extend_interval=False)
        self.update_interval = timedelta(seconds=SCAN_INTERVAL)
        return data

    def _suspend(self, delay: timedelta, *, extend_interval: bool) -> None:
        """Record a cooldown window and optionally defer the next auto refresh."""

        self._suspended_until = dt_util.utcnow() + delay
        if extend_interval:
            # Never auto-poll sooner than both the cooldown and the base cadence.
            self.update_interval = max(delay, timedelta(seconds=SCAN_INTERVAL))
