from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "blueconnect"
DEFAULT_NAME = "Blue Connect"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_BLUE_KEY = "blue_key"

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]
SCAN_INTERVAL = 3600
