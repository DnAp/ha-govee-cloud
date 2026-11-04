"""Constants for the Govee Cloud integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "govee_cloud"

UPDATE_INTERVAL: Final = timedelta(minutes=10)

# Models known to work. Other models are added when they report the same
# temperature/humidity data shape (see coordinator.is_supported_device).
SUPPORTED_SKU: Final = ("H5179",)

# unique_id prefixes, kept from the first versions so entity IDs survive upgrades.
TEMPERATURE_PREFIX: Final = "temp"
HUMIDITY_PREFIX: Final = "hum"
BATTERY_PREFIX: Final = "batt"
ONLINE_PREFIX: Final = "online"
UPLOAD_RATE_PREFIX: Final = "upload_rate"

ISSUE_APP_VERSION: Final = "app_version_too_low"
