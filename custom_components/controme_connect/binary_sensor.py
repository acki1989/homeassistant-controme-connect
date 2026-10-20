"""Support for Controme binary sensors."""
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
from .helpers import room_slug
from .sensor import (
    find_room,
    firmware_update_available,
    is_multi_sensor,
    parse_transmission,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the Controme binary sensor platform."""
    entities = []
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    house_id = entry.data[CONF_HAUS_ID]

    # The firmware of the mini server is not bound to a room
    # The name of the hub device is set in __init__.py, it must not be
    # overwritten here
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
    """Representation of the firmware update state of the mini server."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.UPDATE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:cloud-download-outline"

    def __init__(self, coordinator, config_entry, device_info):
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._device_info = device_info
        self._house_id = config_entry.data[CONF_HAUS_ID]

        self._attr_unique_id = f"{self._house_id}_firmware_update"
        self.entity_id = "binary_sensor.controme_connect_firmware_update"
        self._attr_name = "Firmware-Update verfügbar"

        self._update_from_data()

    @property
    def device_info(self):
        """Return device info for this sensor."""
        return self._device_info

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
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
        """Handle updated data from the coordinator."""
        self._update_from_data()
        self.async_write_ha_state()

    def _update_from_data(self):
        """Update the update state."""
        info = self.coordinator.data.get("info") or {}
        update = self.coordinator.data.get("update") or {}
        self._attr_is_on = firmware_update_available(info, update)


class ContromeTransmissionProblemSensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of the transmission state of the sensors of a room."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:cloud-alert"

    def __init__(self, coordinator, config_entry, room_data, device_info):
        """Initialize the binary sensor."""
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
        self._attr_name = "Übertragung gestört"

        self._update_from_data()

    @property
    def device_info(self):
        """Return device info for this sensor."""
        return self._device_info

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
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
        """Handle updated data from the coordinator."""
        self._update_from_data()
        self.async_write_ha_state()

    def _update_from_data(self):
        """Update the problem state from the last transmissions.

        Every sensor is checked with the timeout of its type. The multi
        sensors (for example the room thermostats with a solar cell) sleep
        between the transmissions, they get a much longer timeout.
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
