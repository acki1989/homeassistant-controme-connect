"""Constants for the Controme integration."""

from datetime import timedelta
from typing import Final
from homeassistant.const import Platform

# Integration domain
DOMAIN: Final = "controme_connect"

# Configuration keys used in the web configuration
CONF_API_URL: Final = "api_url"
CONF_HAUS_ID: Final = "haus_id"
CONF_USER: Final = "user"
CONF_PASSWORD: Final = "password"

# Platforms are now defined in __init__.py

# New constants
SENSOR_TYPE_CURRENT = "current"
SENSOR_TYPE_TARGET = "target"
SENSOR_TYPE_HUMIDITY = "humidity"
SENSOR_TYPE_RETURN = "return"
SENSOR_TYPE_TOTAL_OFFSET = "total_offset"
SENSOR_TYPE_OPERATION_MODE = "operation_mode"

SENSOR_TYPES = {
    SENSOR_TYPE_CURRENT: "temperatur",
    SENSOR_TYPE_TARGET: "solltemperatur",
    SENSOR_TYPE_HUMIDITY: "luftfeuchte",
    SENSOR_TYPE_TOTAL_OFFSET: "total_offset",
    SENSOR_TYPE_OPERATION_MODE: "betriebsart",
}

ENTITY_ID_MAP = {
    SENSOR_TYPE_CURRENT: "temperature",
    SENSOR_TYPE_TARGET: "target",
    SENSOR_TYPE_HUMIDITY: "humidity",
    SENSOR_TYPE_TOTAL_OFFSET: "offset",
    SENSOR_TYPE_OPERATION_MODE: "mode",
}

# Map sensor types to API data keys
VALUE_MAP = {
    SENSOR_TYPE_CURRENT: "temperatur",
    SENSOR_TYPE_TARGET: "solltemperatur",
    SENSOR_TYPE_HUMIDITY: "luftfeuchte",
    SENSOR_TYPE_TOTAL_OFFSET: "total_offset",
    SENSOR_TYPE_OPERATION_MODE: "betriebsart",
}

# Room icons of the Controme web interface mapped to Material Design icons.
# The plain icon name is kept as attribute of the climate entity.
ROOM_ICONS: Final = {
    "sessel": "mdi:sofa",
    "bett": "mdi:bed",
    "dusche": "mdi:shower",
    "punkte": "mdi:dots-horizontal",
    "spiel": "mdi:teddy-bear",
    "feuer": "mdi:fire",
    "messergabel": "mdi:silverware-fork-knife",
    "esstisch": "mdi:table-furniture",
    "toilette": "mdi:toilet",
    "desk": "mdi:desk",
}

# Fallback for rooms with an unknown Controme icon
DEFAULT_ROOM_ICON: Final = "mdi:home-thermometer"

# A sensor is considered stale when it did not report within this period
TRANSMISSION_TIMEOUT: Final = timedelta(minutes=30)

# Battery and solar powered room thermostats (their value is delivered as a
# dictionary) sleep between the transmissions, they report only every few hours
TRANSMISSION_TIMEOUT_MULTI: Final = timedelta(hours=6)

# The firmware update check needs a login to the web interface and is only
# done every few hours
UPDATE_CHECK_INTERVAL: Final = timedelta(hours=6)

# Number of house ids that are queried during the setup
HOUSE_ID_CHECK_COUNT: Final = 10
