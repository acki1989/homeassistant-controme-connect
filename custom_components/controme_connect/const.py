"""Konstanten der Controme-Integration."""

from datetime import timedelta
from typing import Final
from homeassistant.const import Platform

# Domain der Integration
DOMAIN: Final = "controme_connect"

# Schlüssel der Konfiguration über die Weboberfläche
CONF_API_URL: Final = "api_url"
CONF_HAUS_ID: Final = "haus_id"
CONF_USER: Final = "user"
CONF_PASSWORD: Final = "password"

# Die Plattformen werden in __init__.py definiert

# Neue Konstanten
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

# Abbildung der Sensortypen auf die Datenschlüssel der API
VALUE_MAP = {
    SENSOR_TYPE_CURRENT: "temperatur",
    SENSOR_TYPE_TARGET: "solltemperatur",
    SENSOR_TYPE_HUMIDITY: "luftfeuchte",
    SENSOR_TYPE_TOTAL_OFFSET: "total_offset",
    SENSOR_TYPE_OPERATION_MODE: "betriebsart",
}

# Raum-Icons der Controme-Weboberfläche, abgebildet auf Material-Design-Icons.
# Der reine Icon-Name wird als Attribut der Heizungs-Entity behalten.
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

# Ersatz für Räume mit unbekanntem Controme-Icon
DEFAULT_ROOM_ICON: Final = "mdi:home-thermometer"

# Ein Sensor gilt als veraltet, wenn er in diesem Zeitraum nicht gemeldet hat
TRANSMISSION_TIMEOUT: Final = timedelta(minutes=30)

# Batterie- und solarbetriebene Raumthermostate (ihr Wert wird als Dictionary
# geliefert) schlafen zwischen den Übertragungen und melden sich nur alle paar Stunden
TRANSMISSION_TIMEOUT_MULTI: Final = timedelta(hours=6)

# Die Prüfung auf Firmware-Updates braucht einen Login an der Weboberfläche und
# erfolgt nur alle paar Stunden
UPDATE_CHECK_INTERVAL: Final = timedelta(hours=6)

# Anzahl der Haus-IDs, die beim Einrichten abgefragt werden
HOUSE_ID_CHECK_COUNT: Final = 10
