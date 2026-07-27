from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from aiohttp import BasicAuth, ClientError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

API_TIMEOUT = 30
BASE_URL = "https://api.riiotlabs.com/automation/blue/{blue_key}/lastMeasurement"

# Fallback cooldown used when the API reports a rate limit without a duration.
DEFAULT_RATE_LIMIT_SECONDS = 45 * 60

_RETRY_MINUTES_RE = re.compile(r"try again in\s+(\d+)\s+minute", re.IGNORECASE)
_WAIT_MINUTES_RE = re.compile(r"wait at least\s+(\d+)\s+minute", re.IGNORECASE)


class BlueConnectApiError(Exception):
    """Raised when the Blue Connect API request fails."""


class BlueConnectAuthError(BlueConnectApiError):
    """Raised when Blue Connect credentials are invalid."""


class BlueConnectRateLimitError(BlueConnectApiError):
    """Raised when the Blue Connect API rejects a call due to rate limiting."""

    def __init__(self, retry_after: int, message: str | None = None) -> None:
        super().__init__(message or "Blue Connect API rate limit reached")
        self.retry_after = retry_after


class BlueConnectApi:
    """Blue Connect API client."""

    def __init__(self, hass, username: str, password: str, blue_key: str) -> None:
        self._session = async_get_clientsession(hass)
        self._username = username
        self._password = password
        self._blue_key = blue_key

    @property
    def blue_key(self) -> str:
        """Return the configured Blue Key."""

        return self._blue_key

    async def async_get_measurement(self) -> dict[str, Any]:
        """Return the latest Blue Connect measurement.

        The RiiotLabs API is heavily rate limited (roughly one call every 45
        minutes). When the limit is exceeded it responds with an HTTP 500 and a
        JSON body describing how long to wait, which is surfaced as a
        ``BlueConnectRateLimitError`` so callers can back off instead of
        hammering the endpoint.
        """

        auth = BasicAuth(self._username, self._password)
        url = BASE_URL.format(blue_key=self._blue_key)

        try:
            async with asyncio.timeout(API_TIMEOUT):
                async with self._session.get(url, auth=auth) as response:
                    status = response.status
                    body = await response.text()
        except (TimeoutError, ClientError) as err:
            raise BlueConnectApiError(str(err) or "Blue Connect request failed") from err

        payload = _parse_json(body)

        retry_after = _rate_limit_seconds(payload)
        if retry_after is not None:
            raise BlueConnectRateLimitError(retry_after, _payload_message(payload))

        if status in {401, 403}:
            raise BlueConnectAuthError(f"Authentication failed (HTTP {status})")

        if status >= 400:
            raise BlueConnectApiError(f"Blue Connect API returned HTTP {status}")

        if not isinstance(payload, dict):
            raise BlueConnectApiError("Unexpected payload returned by Blue Connect API")

        return payload


def _parse_json(body: str) -> Any:
    """Parse a response body as JSON, returning ``None`` on failure."""

    try:
        return json.loads(body)
    except (ValueError, TypeError):
        return None


def _payload_message(payload: Any) -> str | None:
    """Return the human readable message from an API payload, if present."""

    if isinstance(payload, dict):
        message = payload.get("message")
        if isinstance(message, str):
            return message
    return None


def _rate_limit_seconds(payload: Any) -> int | None:
    """Return the cooldown in seconds if the payload signals a rate limit."""

    message = _payload_message(payload)
    if message is None or "too many calls" not in message.lower():
        return None

    match = _RETRY_MINUTES_RE.search(message) or _WAIT_MINUTES_RE.search(message)
    if match:
        return int(match.group(1)) * 60

    return DEFAULT_RATE_LIMIT_SECONDS
