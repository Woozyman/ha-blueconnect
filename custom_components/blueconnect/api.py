from __future__ import annotations

import asyncio
from typing import Any

from aiohttp import BasicAuth, ClientError, ClientResponseError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

API_TIMEOUT = 30
BASE_URL = "https://api.riiotlabs.com/automation/blue/{blue_key}/lastMeasurement"


class BlueConnectApiError(Exception):
    """Raised when the Blue Connect API request fails."""


class BlueConnectAuthError(BlueConnectApiError):
    """Raised when Blue Connect credentials are invalid."""


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
        """Return the latest Blue Connect measurement."""

        auth = BasicAuth(self._username, self._password)
        url = BASE_URL.format(blue_key=self._blue_key)

        try:
            async with asyncio.timeout(API_TIMEOUT):
                async with self._session.get(url, auth=auth) as response:
                    response.raise_for_status()
                    payload = await response.json()
        except ClientResponseError as err:
            if err.status in {401, 403}:
                raise BlueConnectAuthError from err
            raise BlueConnectApiError from err
        except (TimeoutError, ClientError, ValueError) as err:
            raise BlueConnectApiError from err

        if not isinstance(payload, dict):
            raise BlueConnectApiError("Unexpected payload returned by Blue Connect API")

        return payload
