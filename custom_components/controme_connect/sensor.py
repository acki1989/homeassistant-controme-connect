"""Unterstützung der Sensoren von Controme."""
import logging
import re
import unicodedata
from typing import Any
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfTemperature,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_API_URL,
    CONF_HAUS_ID,
    ENTITY_ID_MAP,
    VALUE_MAP,
    TRANSMISSION_TIMEOUT,
    TRANSMISSION_TIMEOUT_MULTI,
)
from .firmware import parse_version
from .helpers import extract_humidity, extract_multi_sensor_values, room_slug

from dataclasses import dataclass

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=60)

# Die Controme-API kennzeichnet die Rücklauf-Sensoren mit der Kurzbezeichnung "RL"
# (z. B. "Galerie RL"). Andere Firmware-Versionen verwenden stattdessen das ganze Wort.
RETURN_SENSOR_PATTERN = re.compile(r"(rücklauf|ruecklauf|\brl\b)", re.IGNORECASE)

# Umlaute werden transkribiert, damit die Entity-IDs ASCII bleiben
_TRANSLITERATION = str.maketrans(
    {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"}
)

# Die letzte Übertragung wird je nach Endpunkt in verschiedenen Formaten
# gemeldet, alle sind Ortszeiten der Controme-Anlage.
TRANSMISSION_FORMATS = (
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%H:%M:%S %d.%m.%Y",
    "%H:%M %d.%m.%Y",
)


def is_return_sensor(description: str) -> bool:
    """Gibt True zurück, wenn die Sensorbeschreibung einen Rücklauf-Sensor kennzeichnet."""
    return bool(RETURN_SENSOR_PATTERN.search(description or ""))


def return_label(description: str, room_name: str) -> str:
    """Gibt ein kurzes Label zurück, das den Rücklauf-Sensor im Raum beschreibt."""
    label = RETURN_SENSOR_PATTERN.sub(" ", description or "")
    label = re.sub(r"\s+", " ", label).strip(" -_")
    room = (room_name or "").strip()
    if room and label.lower().startswith(room.lower()):
        label = label[len(room):].strip(" -_")
    return label


def slugify(text: str) -> str:
    """Wandelt einen Text in einen ASCII-Slug um, der in Entity-IDs taugt."""
    text = (text or "").translate(_TRANSLITERATION)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def is_active_offset(values: Any) -> bool:
    """Gibt True zurück, wenn ein Modul derzeit einen Offset auf den Raum anwendet."""
    if not isinstance(values, dict) or "raum" not in values:
        return False
    try:
        return float(values["raum"]) != 0
    except (TypeError, ValueError):
        return False


def parse_transmission(value: str) -> datetime | None:
    """Wertet den Zeitstempel der letzten Übertragung eines Controme-Sensors aus."""
    if not value:
        return None
    value = value.strip()
    for timestamp_format in TRANSMISSION_FORMATS:
        try:
            parsed = datetime.strptime(value, timestamp_format)
        except ValueError:
            continue
        # Die Controme-Anlage meldet Ortszeiten
        return parsed.replace(tzinfo=dt_util.now().tzinfo)
    _LOGGER.debug("Unbekanntes Format der letzten Übertragung: %s", value)
    return None


def is_multi_sensor(sensor: Any) -> bool:
    """Gibt True zurück, wenn der Sensor mehrere Werte liefert.

        Die Multi-Sensoren der Controme-Anlage (zum Beispiel die
        Raumthermostate mit Solarzelle) liefern ihre Werte als Dictionary.
        Sie schlafen zwischen den Übertragungen und brauchen deshalb ein
        längeres Zeitlimit.
    """
    return isinstance((sensor or {}).get("wert"), dict)


def find_room(coordinator, floor_id, room_id, fallback=None):
    """Gibt die aktuellen Raumdaten des letzten Coordinator-Updates zurück."""
    for floor in coordinator.data.get("floors", []):
        if floor.get("id") == floor_id:
            for room in floor.get("raeume", []):
                if room.get("id") == room_id:
                    return room
    return fallback


def firmware_update_available(info: Any, update: Any) -> bool | None:
    """Gibt True zurück, wenn die Weboberfläche eine neuere Firmware bietet."""
    if update and update.get("available") is not None:
        return update["available"]
    installed = parse_version((info or {}).get("sw-date", ""))
    latest = parse_version((update or {}).get("version") or "")
    if installed is None or latest is None:
        return None
    return latest > installed


# Zeitpunkt des letzten Reloads und Sperrzeit, damit die Integration nicht
# mehrfach hintereinander neu geladen wird
_last_reload: datetime | None = None
RELOAD_COOLDOWN = timedelta(minutes=10)


@dataclass
class ContromeSensorEntityDescription(SensorEntityDescription):
    """Beschreibt die Sensor-Entity von Controme."""

SENSOR_TYPES: tuple[ContromeSensorEntityDescription, ...] = (
    ContromeSensorEntityDescription(
        key="current",
        translation_key="current",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    ContromeSensorEntityDescription(
        key="target",
        translation_key="target",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    ContromeSensorEntityDescription(
        key="return",
        translation_key="return",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    ContromeSensorEntityDescription(
        key="total_offset",
        translation_key="total_offset",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    ContromeSensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Richtet die Plattform der Sensoren ein."""
    sensors = []
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    data = coordinator.data
    house_id = entry.data[CONF_HAUS_ID]

    # Hub-Gerät erzeugen
    # Der Name des Hub-Geräts wird in __init__.py gesetzt und darf hier
    # nicht überschrieben werden
    hub_device_info = DeviceInfo(
        identifiers={(DOMAIN, house_id)},
    )
    hub_device_id = hass.data[DOMAIN][entry.entry_id].get("hub_device_id")
    entity_registry = er.async_get(hass)

    _LOGGER.debug("Die Controme-Sensoren werden mit diesen Daten eingerichtet: %s", data)

    # Die Firmware des Mini-Servers gehört zu keinem Raum
    sensors.append(
        ContromeFirmwareSensor(
            coordinator,
            entry,
            hub_device_info,
        )
    )

    if not data.get("floors"):
        _LOGGER.error("Vom Coordinator wurden keine Daten empfangen")
        return

    # Alle Etagen und Räume verarbeiten
    for floor in data["floors"]:
        floor_id = floor.get("id")
        floor_name = floor.get("etagenname", f"Floor {floor_id}")
        rooms = floor.get("raeume", [])
        _LOGGER.debug("Etagen %s wird mit den Räumen verarbeitet: %s", floor_id, rooms)

        if not rooms and ("temperatur" in floor or "solltemperatur" in floor):
            rooms = [floor]
            _LOGGER.debug("Die Etage wird als Raum verwendet, weil keine Räume gefunden wurden")

        for index, room in enumerate(rooms):
            room_id = room.get("id")
            if not room_id:
                room_id = f"{floor_id}_{index}"
            room_name = room.get("name", f"Room {room_id}")
            _LOGGER.debug("Raum %s wird mit diesen Daten verarbeitet: %s", room_name, room)

            # Raumdaten hinzufügen
            room["floor_id"] = floor_id
            device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{house_id}_{floor_id}_{room_id}")},
                name=room_name,
                manufacturer="Controme",
                model="Room",
                via_device_id=hub_device_id,
            )

            # Grundsensoren hinzufügen
            for sensor_type, data_key in VALUE_MAP.items():
                _LOGGER.debug("Es wird nach dem Sensor %s (Schlüssel: %s) in den Raumdaten gesucht: %s",
                            sensor_type, data_key, data_key in room)
                if data_key in room:
                    _LOGGER.debug("Sensor %s wird für den Raum %s hinzugefügt", sensor_type, room_name)
                    if sensor_type == "operation_mode":
                        sensor_class = ContromeOperationModeSensor
                    else:
                        sensor_class = ContromeSensor
                    sensors.append(
                        sensor_class(
                            coordinator,
                            entry,
                            room,
                            sensor_type,
                            device_info,
                        )
                    )
                    _LOGGER.debug("Sensor %s hinzugefügt", sensor_type)

            # Rücklauftemperatur-Sensoren verarbeiten
            return_sensors = [
                sensor
                for sensor in room.get("sensoren", [])
                if is_return_sensor(sensor.get("beschreibung", ""))
            ]
            used_slugs: set[str] = set()
            for index, sensor in enumerate(return_sensors):
                description = sensor.get("beschreibung", "")
                label = return_label(description, room.get("name", ""))
                slug = slugify(label)
                if not slug or slug in used_slugs:
                    # Ohne eindeutiges Label muss der Index die Eindeutigkeit
                    # sicherstellen, sonst kollidieren die Entity-IDs
                    slug = f"{slug}_{index + 1}" if slug else f"rl_{index + 1}"
                    while slug in used_slugs:
                        slug = f"{slug}_{index + 1}"
                used_slugs.add(slug)
                _LOGGER.debug("Rücklauf-Sensor %s (%s) wird für den Raum %s hinzugefügt",
                              sensor.get("name"), description, room_name)
                sensors.append(
                    ContromeSensor(
                        coordinator,
                        entry,
                        room,
                        f"return_{sensor.get('name')}",
                        device_info,
                        return_label=label,
                        return_slug=slug,
                        return_total=len(return_sensors),
                    )
                )
                _LOGGER.debug("Rücklauf-Sensor hinzugefügt")

            # Module, die den Raum derzeit beeinflussen
            active_plugins = [
                plugin
                for plugin, values in (room.get("offsets") or {}).items()
                if is_active_offset(values)
            ]

            # Abweichung zwischen Ist- und Zieltemperatur. Sie beobachtet außerdem
            # die Offsets des Raums und aktiviert die Entity eines Moduls,
            # das den Raum später zu beeinflussen beginnt.
            sensors.append(
                ContromeDeviationSensor(
                    coordinator,
                    entry,
                    room,
                    device_info,
                    known_offsets=set(active_plugins),
                )
            )

            # Letzte Übertragung der Sensoren des Raums
            sensors.append(
                ContromeLastTransmissionSensor(
                    coordinator,
                    entry,
                    room,
                    device_info,
                )
            )

            # Offset jedes Moduls, das den Raum derzeit beeinflusst. Die
            # Entities der inaktiven Module sind deaktiviert, damit nur
            # die Module erscheinen, die den Sollwert wirklich verschieben.
            for plugin, values in (room.get("offsets") or {}).items():
                if not isinstance(values, dict) or "raum" not in values:
                    continue
                unique_id = f"{house_id}_{floor_id}_{room_id}_offset_{slugify(plugin)}"
                active = is_active_offset(values)
                entity_id = entity_registry.async_get_entity_id(
                    "sensor", DOMAIN, unique_id
                )
                if entity_id:
                    registry_entry = entity_registry.async_get(entity_id)
                    if active and registry_entry.disabled:
                        # Das Modul beeinflusst den Raum wieder
                        entity_registry.async_update_entity(
                            entity_id, disabled_by=None
                        )
                    elif not active and not registry_entry.disabled:
                        # Das Modul beeinflusst den Raum derzeit nicht
                        entity_registry.async_update_entity(
                            entity_id,
                            disabled_by=er.RegistryEntryDisabler.INTEGRATION,
                        )
                sensors.append(
                    ContromeOffsetSensor(
                        coordinator,
                        entry,
                        room,
                        device_info,
                        plugin,
                        enabled=active,
                    )
                )

    _LOGGER.debug("Insgesamt %d Sensoren erzeugt", len(sensors))
    async_add_entities(sensors)

class ContromeSensor(CoordinatorEntity, SensorEntity):
    """Abbildung eines Controme-Sensors."""

    _attr_has_entity_name = True

    def __init_sensor_description(self, sensor_type: str) -> None:
        """Initialisiert die Beschreibung des Sensors anhand des Typs."""
        base_type = sensor_type.split("_")[0]
        self.entity_description = next(
            (desc for desc in SENSOR_TYPES if desc.key == sensor_type),
            next(
                (desc for desc in SENSOR_TYPES if desc.key == base_type),
                SENSOR_TYPES[0],  # Fallback to temperature sensor
            ),
        )

    def __init_entity_id(self, sensor_type: str, room_name: str) -> None:
        """Initialisiert die Entity-ID."""
        room_name_lower = room_slug(room_name)
        suffix = (
            "return"
            if sensor_type.startswith("return_")
            else ENTITY_ID_MAP.get(sensor_type, sensor_type)
        )
        entity_id = f"sensor.controme_connect_{room_name_lower}_{suffix}"
        if sensor_type.startswith("return_") and self._return_total > 1 and self._return_slug:
            entity_id = f"{entity_id}_{self._return_slug}"
        self.entity_id = entity_id

    def __init_name(self, sensor_type: str) -> None:
        """Initialisiert den Namen des Sensors."""
        base_type = sensor_type.split("_")[0]
        if base_type == "return" and self._return_total > 1 and self._return_label:
            # Bei mehreren Rücklauf-Sensoren im Raum trennt das Label sie
            self._attr_translation_key = "return_labeled"
            self._attr_translation_placeholders = {"label": self._return_label}
        else:
            # Der Name kommt aus der Übersetzung der Integration
            self._attr_translation_key = self.entity_description.translation_key

    def __init__(self, coordinator, config_entry, room_data, sensor_type, device_info,
                 return_label: str = "", return_slug: str = "", return_total: int = 1):
        """Initialisiert den Sensor."""
        super().__init__(coordinator)
        _LOGGER.debug("Sensor vom Typ %s wird für den Raum %s initialisiert",
                    sensor_type, room_data.get("name"))

        # Grundattribute setzen
        self._config_entry = config_entry
        self._device_info = device_info
        self._room_data = room_data
        self._sensor_type = sensor_type
        self._room_id = room_data.get("id")
        self._floor_id = room_data.get("floor_id")
        self._house_id = config_entry.data[CONF_HAUS_ID]
        self._base_url = config_entry.data[CONF_API_URL].rstrip('/')
        self._return_label = return_label
        self._return_slug = return_slug
        self._return_total = return_total
        self._humidity_source: str | None = None
        self._multi_sensor_values: dict[str, Any] = {}

        # Unique-ID und Entity-ID setzen
        self._attr_unique_id = f"{self._house_id}_{self._floor_id}_{self._room_id}_{sensor_type}"
        self.__init_sensor_description(sensor_type)
        self.__init_entity_id(sensor_type, room_data.get("name", ""))
        self.__init_name(sensor_type)

        # Anfangswerte setzen
        self._update_from_data(room_data)

    @property
    def device_info(self):
        """Gibt die Geräteinformationen dieses Sensors zurück."""
        return self._device_info

    @property
    def extra_state_attributes(self):
        """Gibt die Zustandsattribute zurück."""
        attributes = {
            "room_id": self._room_id,
            "floor_id": self._floor_id,
            "house_id": self._house_id,
        }
        if self._sensor_type == "humidity":
            # Herkunft der Luftfeuchte und die übrigen Werte der
            # Multi-Sensoren (Helligkeit, Bewegung)
            attributes["source"] = self._humidity_source
            attributes.update(self._multi_sensor_values)
        return attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        """Verarbeitet die aktualisierten Daten des Coordinators."""
        room_data = find_room(
            self.coordinator, self._floor_id, self._room_id, self._room_data
        )
        if room_data is not None:
            self._update_from_data(room_data)
        self.async_write_ha_state()

    def _update_from_data(self, room_data):
        """Aktualisiert den Zustand des Sensors aus den Raumdaten."""
        if self._sensor_type.startswith("return_"):
            found = False
            for sensor in room_data.get("sensoren", []):
                sensor_id = "_".join(self._sensor_type.split("_")[1:])
                if sensor.get("name") == sensor_id:
                    found = True
                    value = sensor.get("wert")
                    try:
                        self._attr_native_value = float(value)
                        self._attr_available = True
                    except (TypeError, ValueError):
                        self._attr_native_value = None
                        self._attr_available = False
                    break
            if not found:
                # Der Sensor wird von der Anlage nicht mehr geliefert
                self._attr_native_value = None
                self._attr_available = False
        else:
            value = room_data.get(VALUE_MAP.get(self._sensor_type))
            # Bei numerischen Sensoren sicherstellen, dass die Werte Zahlen sind
            if self.entity_description.device_class in [
                SensorDeviceClass.TEMPERATURE,
                SensorDeviceClass.HUMIDITY
            ]:
                if self._sensor_type == "humidity":
                    # Die Luftfeuchte kann auch Teil eines Multi-Sensor-Werts sein
                    humidity, source = extract_humidity(room_data)
                    self._attr_native_value = humidity
                    self._attr_available = humidity is not None
                    self._humidity_source = source
                    self._multi_sensor_values = extract_multi_sensor_values(room_data)
                elif not value or (
                    isinstance(value, str)
                    and not value.replace(".", "", 1).isdigit()
                ):
                    self._attr_native_value = None
                    self._attr_available = False
                else:
                    try:
                        self._attr_native_value = float(value) if value is not None else None
                        if self._sensor_type == "total_offset":
                            # Die API liefert die Offsets mit vielen Nachkommastellen
                            self._attr_native_value = round(self._attr_native_value, 2)
                        self._attr_available = True
                    except (ValueError, TypeError):
                        self._attr_native_value = None
                        self._attr_available = False
            else:
                self._attr_native_value = value
                self._attr_available = value is not None


class ContromeFirmwareSensor(CoordinatorEntity, SensorEntity):
    """Abbildung der Firmware des Controme-Mini-Servers."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:chip"

    def __init__(self, coordinator, config_entry, device_info):
        """Initialisiert den Sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._device_info = device_info
        self._house_id = config_entry.data[CONF_HAUS_ID]

        self._attr_unique_id = f"{self._house_id}_firmware"
        self.entity_id = "sensor.controme_connect_firmware"
        self._attr_translation_key = "firmware"

        self._update_from_data()

    @property
    def device_info(self):
        """Gibt die Geräteinformationen dieses Sensors zurück."""
        return self._device_info

    @property
    def extra_state_attributes(self):
        """Gibt die Zustandsattribute zurück."""
        info = self.coordinator.data.get("info") or {}
        update = self.coordinator.data.get("update") or {}
        section = update.get("update_section") or {}
        return {
            "sw_date": info.get("sw-date"),
            "branch": info.get("branch"),
            "commit": info.get("commit"),
            "repo": info.get("repo"),
            "os": info.get("os"),
            "hw": info.get("hw"),
            "fbi": info.get("fbi"),
            "app_compatibility": info.get("app-compatibility"),
            "services_paket": info.get("services-paket"),
            "installed_branch": section.get("installed_branch"),
            "houses": self.coordinator.data.get("houses") or [],
            "installed_build": section.get("installed_build"),
            "miniserver": section.get("miniserver"),
            "uptime_since": section.get("uptime_since"),
            "system_time": section.get("system_time"),
            "latest_version": update.get("version"),
            "lab_version": update.get("lab_version"),
            "update_available": firmware_update_available(info, update),
            "update_status": update.get("status"),
            "update_attempts": update.get("attempts"),
            "available_versions": update.get("versions"),
            "system_check": update.get("overview"),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Verarbeitet die aktualisierten Daten des Coordinators."""
        self._update_from_data()
        self.async_write_ha_state()

    def _update_from_data(self):
        """Aktualisiert die Firmware-Version."""
        info = self.coordinator.data.get("info") or {}
        version = info.get("sw-date")
        self._attr_native_value = version
        self._attr_available = bool(version)


class ContromeDeviationSensor(CoordinatorEntity, SensorEntity):
    """Abbildung der Abweichung zwischen Ist- und Zieltemperatur."""

    _attr_has_entity_name = True
    _attr_device_class = None
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:delta"

    def __init__(self, coordinator, config_entry, room_data, device_info,
                 known_offsets=None):
        """Initialisiert den Sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._device_info = device_info
        self._room_data = room_data
        self._room_id = room_data.get("id")
        self._floor_id = room_data.get("floor_id")
        self._house_id = config_entry.data[CONF_HAUS_ID]
        self._known_offsets: set[str] = known_offsets if known_offsets is not None else set()

        room_name = room_data.get("name", "")
        self._attr_unique_id = f"{self._house_id}_{self._floor_id}_{self._room_id}_deviation"
        self.entity_id = f"sensor.controme_connect_{room_slug(room_name)}_deviation"
        self._attr_translation_key = "deviation"

        self._update_from_data()

    @property
    def device_info(self):
        """Gibt die Geräteinformationen dieses Sensors zurück."""
        return self._device_info

    @property
    def extra_state_attributes(self):
        """Gibt die Zustandsattribute zurück."""
        return {
            "room_id": self._room_id,
            "floor_id": self._floor_id,
            "house_id": self._house_id,
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Verarbeitet die aktualisierten Daten des Coordinators."""
        self._update_from_data()
        self.async_write_ha_state()

    def _update_from_data(self):
        """Aktualisiert die Abweichung aus den Daten des Coordinators."""
        deviation = (self.coordinator.data.get("deviation") or {}).get(self._room_id) or {}
        value = deviation.get("deviation")
        try:
            # Die API liefert die Abweichung mit vielen Nachkommastellen
            self._attr_native_value = round(float(value), 2)
            self._attr_available = True
        except (TypeError, ValueError):
            self._attr_native_value = None
            self._attr_available = False

        self._check_offset_plugins()

    def _check_offset_plugins(self):
        """Lädt die Integration neu, wenn ein Modul den Raum zu beeinflussen beginnt.

            Die Entities der inaktiven Module sind beim Start der Integration
            deaktiviert. Beginnt ein Modul später den Raum zu beeinflussen,
            zum Beispiel die Wetterkorrektur in der Heizsaison, wird die
            Integration neu geladen und die Entities werden neu eingerichtet.
        """
        if self.hass is None:
            return

        room_data = find_room(
            self.coordinator, self._floor_id, self._room_id, self._room_data
        ) or {}

        global _last_reload

        for plugin, values in (room_data.get("offsets") or {}).items():
            if plugin in self._known_offsets:
                continue
            if not is_active_offset(values):
                continue
            self._known_offsets.add(plugin)
            _LOGGER.info(
                "Modul %s beeinflusst jetzt den Raum %s, Integration wird neu geladen",
                plugin,
                room_data.get("name"),
            )
            now = dt_util.utcnow()
            if _last_reload is not None and now - _last_reload < RELOAD_COOLDOWN:
                return
            _last_reload = now
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self._config_entry.entry_id)
            )
            return


class ContromeLastTransmissionSensor(CoordinatorEntity, SensorEntity):
    """Abbildung der letzten Übertragung der Sensoren eines Raums."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, coordinator, config_entry, room_data, device_info):
        """Initialisiert den Sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._device_info = device_info
        self._room_data = room_data
        self._room_id = room_data.get("id")
        self._floor_id = room_data.get("floor_id")
        self._house_id = config_entry.data[CONF_HAUS_ID]
        self._timestamps: dict[str, datetime] = {}
        self._oldest_sensor: str | None = None
        self._oldest_transmission: datetime | None = None

        room_name = room_data.get("name", "")
        self._attr_unique_id = (
            f"{self._house_id}_{self._floor_id}_{self._room_id}_last_transmission"
        )
        self.entity_id = f"sensor.controme_connect_{room_slug(room_name)}_last_transmission"
        self._attr_translation_key = "last_transmission"

        self._update_from_data()

    @property
    def device_info(self):
        """Gibt die Geräteinformationen dieses Sensors zurück."""
        return self._device_info

    @property
    def extra_state_attributes(self):
        """Gibt die Zustandsattribute zurück."""
        now = dt_util.now()
        return {
            "room_id": self._room_id,
            "floor_id": self._floor_id,
            "house_id": self._house_id,
            "oldest_sensor": self._oldest_sensor,
            "oldest_transmission": (
                self._oldest_transmission.isoformat()
                if self._oldest_transmission is not None
                else None
            ),
            "timeout_minutes": int(TRANSMISSION_TIMEOUT.total_seconds() // 60),
            "timeout_minutes_multi": int(
                TRANSMISSION_TIMEOUT_MULTI.total_seconds() // 60
            ),
            "sensors": {
                name: {
                    "transmission": timestamp.isoformat(),
                    "age_minutes": round((now - timestamp).total_seconds() / 60, 1),
                }
                for name, timestamp in self._timestamps.items()
            },
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Verarbeitet die aktualisierten Daten des Coordinators."""
        self._update_from_data()
        self.async_write_ha_state()

    def _update_from_data(self):
        """Aktualisiert die letzte Übertragung der Raumsensoren."""
        room_data = find_room(
            self.coordinator, self._floor_id, self._room_id, self._room_data
        ) or {}

        timestamps: dict[str, datetime] = {}
        newest: datetime | None = None
        oldest: datetime | None = None
        oldest_sensor: str | None = None
        for sensor in room_data.get("sensoren", []):
            parsed = parse_transmission(sensor.get("letzte_uebertragung", ""))
            if parsed is None:
                continue
            name = sensor.get("beschreibung") or sensor.get("name")
            timestamps[name] = parsed
            if newest is None or parsed > newest:
                newest = parsed
            if oldest is None or parsed < oldest:
                oldest = parsed
                oldest_sensor = name

        self._timestamps = timestamps
        self._oldest_sensor = oldest_sensor
        self._oldest_transmission = oldest
        # Die jüngste Übertragung zeigt, wie aktuell die Daten des Raums sind
        self._attr_native_value = newest
        self._attr_available = newest is not None


class ContromeOffsetSensor(CoordinatorEntity, SensorEntity):
    """Abbildung des Offsets, den ein einzelnes Modul auf einen Raum anwendet."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, config_entry, room_data, device_info, plugin,
                 enabled: bool = True):
        """Initialisiert den Sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._device_info = device_info
        self._room_data = room_data
        self._room_id = room_data.get("id")
        self._floor_id = room_data.get("floor_id")
        self._house_id = config_entry.data[CONF_HAUS_ID]
        self._plugin = plugin
        self._house_offset: float | None = None
        # Ein Modul, das den Raum nicht beeinflusst, ist deaktiviert, damit
        # nur die aktiven Module erscheinen.
        self._attr_entity_registry_enabled_default = enabled

        room_name = room_data.get("name", "")
        plugin_slug = slugify(plugin)
        self._attr_unique_id = (
            f"{self._house_id}_{self._floor_id}_{self._room_id}"
            f"_offset_{plugin_slug}"
        )
        self.entity_id = f"sensor.controme_connect_{room_slug(room_name)}_offset_{plugin_slug}"
        self._attr_translation_key = "offset"
        self._attr_translation_placeholders = {"plugin": plugin}

        self._update_from_data()

    @property
    def device_info(self):
        """Gibt die Geräteinformationen dieses Sensors zurück."""
        return self._device_info

    @property
    def extra_state_attributes(self):
        """Gibt die Zustandsattribute zurück."""
        return {
            "room_id": self._room_id,
            "floor_id": self._floor_id,
            "house_id": self._house_id,
            "plugin": self._plugin,
            "house_offset": self._house_offset,
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Verarbeitet die aktualisierten Daten des Coordinators."""
        self._update_from_data()
        self.async_write_ha_state()

    def _update_from_data(self):
        """Aktualisiert den Offset des Moduls."""
        room_data = find_room(
            self.coordinator, self._floor_id, self._room_id, self._room_data
        ) or {}
        values = (room_data.get("offsets") or {}).get(self._plugin) or {}
        try:
            # Die API liefert die Offsets mit vielen Nachkommastellen
            self._attr_native_value = round(float(values.get("raum")), 2)
            self._attr_available = True
        except (TypeError, ValueError):
            self._attr_native_value = None
            self._attr_available = False
        try:
            self._house_offset = round(float(values.get("haus")), 2)
        except (TypeError, ValueError):
            self._house_offset = None


class ContromeOperationModeSensor(CoordinatorEntity, SensorEntity):
    """Abbildung eines Controme-Sensors für die Betriebsart."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, config_entry, room_data, sensor_type, device_info):
        """Initialisiert den Sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._device_info = device_info
        self._room_data = room_data
        self._room_id = room_data.get("id")
        self._floor_id = room_data.get("floor_id")
        self._house_id = config_entry.data[CONF_HAUS_ID]

        # Unique-ID und Entity-ID setzen
        self._attr_unique_id = f"{self._house_id}_{self._floor_id}_{self._room_id}_operation_mode"
        room_name = room_data.get("name", "")
        room_name_lower = room_slug(room_name)
        self.entity_id = f"sensor.controme_connect_{room_name_lower}_mode"

        # Beschreibung der Entity setzen
        self.entity_description = ContromeSensorEntityDescription(
            key="operation_mode",
            translation_key="operation_mode",
            device_class=None,
            state_class=None,
            native_unit_of_measurement=None,
            has_entity_name=True,
        )

        # Namen setzen
        self._attr_translation_key = "operation_mode"

        # Anfangswert und Verfügbarkeit setzen
        self._update_from_data(room_data)

    @property
    def device_info(self):
        """Gibt die Geräteinformationen dieses Sensors zurück."""
        return self._device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Verarbeitet die aktualisierten Daten des Coordinators."""
        updated = False
        for floor in self.coordinator.data.get("floors", []):
            if floor["id"] == self._floor_id:
                for room in floor.get("raeume", []):
                    if room["id"] == self._room_id:
                        self._update_from_data(room)
                        updated = True
                        break
                if updated:
                    break

        self.async_write_ha_state()

    def _update_from_data(self, room_data):
        """Aktualisiert den Zustand des Sensors aus den Raumdaten."""
        value = room_data.get(VALUE_MAP["operation_mode"])
        if isinstance(value, str):
            # Die Anlage liefert "Heating" mit großem H. Die Schlüssel der
            # Zustandsübersetzungen müssen klein geschrieben sein.
            value = value.lower()
        self._attr_native_value = value
        self._attr_available = value is not None
