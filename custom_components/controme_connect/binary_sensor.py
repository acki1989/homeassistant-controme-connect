"""Unterstützung der binären Sensoren von Controme."""
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_HAUS_ID,
    TRANSMISSION_TIMEOUT,
    TRANSMISSION_TIMEOUT_MULTI,
)
from .helpers import parse_transmission, room_slug
from .sensor import (
    find_room,
    firmware_update_available,
    is_multi_sensor,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Richtet die Plattform der binären Sensoren ein."""
    entities = []
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    house_id = entry.data[CONF_HAUS_ID]

    # Die Firmware des Mini-Servers gehört zu keinem Raum
    # Der Name des Hub-Geräts wird in __init__.py gesetzt und darf hier
    # nicht überschrieben werden
    hub_device_info = DeviceInfo(
        identifiers={(DOMAIN, house_id)},
    )
    hub_device_id = hass.data[DOMAIN][entry.entry_id].get("hub_device_id")
    entities.append(
        ContromeFirmwareUpdateSensor(
            coordinator,
            entry,
            hub_device_info,
        )
    )

    for floor in coordinator.data.get("floors", []):
        floor_id = floor.get("id")
        rooms = floor.get("raeume", [])

        if not rooms and ("temperatur" in floor or "solltemperatur" in floor):
            rooms = [floor]

        for room in rooms:
            room_id = room.get("id")
            if not room_id:
                continue
            room["floor_id"] = floor_id
            device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{house_id}_{floor_id}_{room_id}")},
                name=room.get("name", f"Room {room_id}"),
                manufacturer="Controme",
                model="Room",
                via_device_id=hub_device_id,
            )
            entities.append(
                ContromeTransmissionProblemSensor(
                    coordinator,
                    entry,
                    room,
                    device_info,
                )
            )

    async_add_entities(entities)


class ContromeFirmwareUpdateSensor(CoordinatorEntity, BinarySensorEntity):
    """Abbildung des Firmware-Update-Status des Mini-Servers."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.UPDATE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:cloud-download-outline"

    def __init__(self, coordinator, config_entry, device_info):
        """Initialisiert den binären Sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._device_info = device_info
        self._house_id = config_entry.data[CONF_HAUS_ID]

        self._attr_unique_id = f"{self._house_id}_firmware_update"
        self.entity_id = "binary_sensor.controme_connect_firmware_update"
        self._attr_translation_key = "firmware_update"

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
            "installed_version": info.get("sw-date"),
            "installed_build": section.get("installed_build"),
            "installed_branch": section.get("installed_branch"),
            "latest_version": update.get("version"),
            "lab_version": update.get("lab_version"),
            "update_status": update.get("status"),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Verarbeitet die aktualisierten Daten des Coordinators."""
        self._update_from_data()
        self.async_write_ha_state()

    def _update_from_data(self):
        """Aktualisiert den Update-Status."""
        info = self.coordinator.data.get("info") or {}
        update = self.coordinator.data.get("update") or {}
        self._attr_is_on = firmware_update_available(info, update)


class ContromeTransmissionProblemSensor(CoordinatorEntity, BinarySensorEntity):
    """Abbildung des Übertragungsstatus der Sensoren eines Raums."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:cloud-alert"

    def __init__(self, coordinator, config_entry, room_data, device_info):
        """Initialisiert den binären Sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._device_info = device_info
        self._room_data = room_data
        self._room_id = room_data.get("id")
        self._floor_id = room_data.get("floor_id")
        self._house_id = config_entry.data[CONF_HAUS_ID]
        self._oldest_sensor: str | None = None
        self._stale_sensors: list[str] = []

        room_name = room_data.get("name", "")
        self._attr_unique_id = (
            f"{self._house_id}_{self._floor_id}_{self._room_id}"
            "_transmission_problem"
        )
        self.entity_id = (
            f"binary_sensor.controme_connect_{room_slug(room_name)}"
            "_transmission_problem"
        )
        self._attr_translation_key = "transmission_problem"

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
            "oldest_sensor": self._oldest_sensor,
            "stale_sensors": self._stale_sensors,
            "timeout_minutes": int(TRANSMISSION_TIMEOUT.total_seconds() // 60),
            "timeout_minutes_multi": int(
                TRANSMISSION_TIMEOUT_MULTI.total_seconds() // 60
            ),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Verarbeitet die aktualisierten Daten des Coordinators."""
        self._update_from_data()
        self.async_write_ha_state()

    def _update_from_data(self):
        """Aktualisiert den Problemstatus aus den letzten Übertragungen.

            Jeder Sensor wird mit dem Zeitlimit seines Typs geprüft. Die
            Multi-Sensoren (zum Beispiel die Raumthermostate mit Solarzelle)
            schlafen zwischen den Übertragungen und erhalten ein deutlich
            längeres Zeitlimit.
        """
        room_data = find_room(
            self.coordinator, self._floor_id, self._room_id, self._room_data
        ) or {}

        now = dt_util.now()
        oldest = None
        oldest_sensor = None
        stale_sensors = []
        for sensor in room_data.get("sensoren", []):
            parsed = parse_transmission(sensor.get("letzte_uebertragung", ""))
            if parsed is None:
                continue
            name = sensor.get("beschreibung") or sensor.get("name")
            if oldest is None or parsed < oldest:
                oldest = parsed
                oldest_sensor = name
            timeout = (
                TRANSMISSION_TIMEOUT_MULTI
                if is_multi_sensor(sensor)
                else TRANSMISSION_TIMEOUT
            )
            if now - parsed > timeout:
                stale_sensors.append(name)

        self._oldest_sensor = oldest_sensor
        self._stale_sensors = stale_sensors
        if oldest is None:
            self._attr_is_on = None
            return
        self._attr_is_on = bool(stale_sensors)
