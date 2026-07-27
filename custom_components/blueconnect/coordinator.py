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
        self._allowed_after: datetime | None = None
        self._next_poll: datetime | None = None

    @property
    def next_update(self) -> datetime | None:
        """Return when the next automatic API poll is scheduled, if known."""

        return self._next_poll

    @property
    def call_allowed(self) -> bool:
        """Return whether the API may be called right now."""

        return self._allowed_after is None or dt_util.utcnow() >= self._allowed_after

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Blue Connect API, honouring the API's limits."""

        now = dt_util.utcnow()

        # Never call the API before the minimum spacing has elapsed. This
        # protects the fragile endpoint from manual refreshes, reloads or
        # restarts hammering it.
        if self._allowed_after is not None and now < self._allowed_after:
            remaining = int((self._allowed_after - now).total_seconds())
            _LOGGER.debug(
                "Skipping Blue Connect update; %s seconds until next allowed call",
                remaining,
            )
            return self.data if self.data is not None else {}

        try:
            data = await self.api.async_get_measurement()
        except BlueConnectAuthError as err:
            raise ConfigEntryAuthFailed from err
        except BlueConnectRateLimitError as err:
            delay = timedelta(seconds=max(err.retry_after, 0)) + RATE_LIMIT_BUFFER
            self._reschedule(gate=delay, cadence=delay)
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

        # Success: poll again on the normal ~hourly cadence, while still
        # honouring the API's ~45 minute minimum spacing for manual refreshes.
        self._reschedule(gate=MIN_CALL_SPACING + RATE_LIMIT_BUFFER, cadence=timedelta(seconds=SCAN_INTERVAL))
        return data

    def _reschedule(self, *, gate: timedelta, cadence: timedelta) -> None:
        """Record the next allowed call time and the next automatic poll."""

        now = dt_util.utcnow()
        self._allowed_after = now + gate
        self.update_interval = cadence
        self._next_poll = now + cadence
