"""Unterstützung der Heizungs-Entities von Controme."""
import logging
from typing import Any
from datetime import timedelta

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from aiohttp import ClientTimeout
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_API_URL, CONF_HAUS_ID, CONF_USER, CONF_PASSWORD
from .helpers import extract_humidity, room_icon, room_slug

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=60)
REQUEST_TIMEOUT = ClientTimeout(total=10)  # 10 Sekunden Timeout
ATTR_HUMIDITY = "current_humidity"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Richtet die Plattform der Heizungs-Entities ein."""
    climate_devices = []
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    data = coordinator.data
    house_id = entry.data[CONF_HAUS_ID]
    room_icons = data.get("rooms", {})
    hub_device_id = hass.data[DOMAIN][entry.entry_id].get("hub_device_id")

    # Alle Etagen und Räume verarbeiten
    for floor in data.get("floors", []):
        floor_id = floor.get("id")
        floor_name = floor.get("etagenname", f"Floor {floor_id}")
        rooms = floor.get("raeume", [])

        if not rooms and ("temperatur" in floor or "solltemperatur" in floor):
            rooms = [floor]

        for index, room in enumerate(rooms):
            room_id = room.get("id")
            if not room_id:
                room_id = f"{floor_id}_{index}"
            room_name = room.get("name", f"Room {room_id}")
            room["floor_id"] = floor_id

            device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{house_id}_{floor_id}_{room_id}")},
                name=room_name,
                manufacturer="Controme",
                model="Thermostat API",
                via_device_id=hub_device_id,
            )

            climate_devices.append(
                ContromeClimate(
                    coordinator,
                    entry,
                    room,
                    device_info,
                    room_icons.get(room_id, ""),
                )
            )

    async_add_entities(climate_devices)

class ContromeClimate(CoordinatorEntity, ClimateEntity):
    """Abbildung einer Controme-Heizung."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, coordinator, config_entry, room_data, device_info, controme_icon=""):
        """Initialisiert die Heizung."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._base_url = config_entry.data[CONF_API_URL].rstrip('/')
        self._device_info = device_info
        self._room_data = room_data
        self._attr_name = room_data.get("name")
        self._room_id = room_data.get("id")
        self._floor_id = room_data.get("floor_id")
        self._house_id = config_entry.data[CONF_HAUS_ID]
        self._user = config_entry.data[CONF_USER]
        self._password = config_entry.data[CONF_PASSWORD]
        self._attr_unique_id = (
            f"{config_entry.data[CONF_HAUS_ID]}_{self._floor_id}_{self._room_id}"
            "_climate"
        )
        self.entity_id = f"climate.controme_connect_{room_slug(self._attr_name)}"
        self._update_from_data(room_data)

        # Raum-Icon der Controme-Weboberfläche
        self._controme_icon = controme_icon
        self._attr_icon = room_icon(controme_icon)

        # Unterstützte Funktionen setzen
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
        )

        # Temperatur-Einstellungen setzen
        self._attr_target_temperature_step = 0.5
        self._attr_min_temp = 5
        self._attr_max_temp = 30
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS

        # Betriebsarten setzen
        self._attr_hvac_modes = [
            HVACMode.HEAT,
            HVACMode.OFF,
        ]

    def _update_from_data(self, data):
        """Aktualisiert die Attribute aus den Daten."""
        self._attr_current_temperature = data.get("temperatur")
        self._attr_target_temperature = data.get("solltemperatur")
        self._attr_hvac_mode = HVACMode.HEAT if data.get("betriebsart") == "Heating" else None
        # Die API liefert Text, wenn kein Feuchtesensor vorhanden ist
        humidity, _ = extract_humidity(data)
        self._attr_current_humidity = humidity
        self._temporary_mode = bool(data.get("is_temporary_mode"))
        self._remaining_time = data.get("remaining_time")
        self._mode_end_datetime = data.get("mode_end_datetime")
        self._perm_target_temperature = data.get("perm_solltemperatur")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Verarbeitet die aktualisierten Daten des Coordinators."""
        for floor in self.coordinator.data.get("floors", []):
            if floor.get("id") == self._floor_id:
                for room in floor.get("raeume", []):
                    if room.get("id") == self._room_id:
                        self._update_from_data(room)
                        break
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Gibt die Geräteinformationen zurück."""
        return self._device_info

    @property
    def extra_state_attributes(self):
        """Gibt die optionalen Zustandsattribute zurück."""
        return {
            ATTR_HUMIDITY: self._attr_current_humidity,
            "is_temporary_mode": self._temporary_mode,
            "remaining_time": self._remaining_time,
            "mode_end_datetime": self._mode_end_datetime,
            "perm_target_temperature": self._perm_target_temperature,
            "controme_icon": self._controme_icon,
        }

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Setzt die neue Zieltemperatur."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        session = async_get_clientsession(self.hass)
        # Abschließenden Slash der Basis-URL entfernen, falls vorhanden
        base_url = self._base_url.rstrip('/')
        endpoint = f"{base_url}/set/json/v1/{self._house_id}/soll/{self._room_id}/"

        data = {
            "user": self._user,
            "password": self._password,
            "soll": str(float(temperature))
        }

        try:
            # Anfragedetails zur Fehlersuche protokollieren
            _LOGGER.debug(
                "Zieltemperatur wird gesetzt: URL=%s, Daten=%s",
                endpoint,
                {**data, "password": "***"},
            )

            async with session.post(
                endpoint,
                data=data,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Accept': 'application/json'
                }
            ) as response:
                response_text = await response.text()
                if response.status != 200:
                    if response.status == 403:
                        _LOGGER.error(
                            "Die Anmeldung ist beim Setzen der Temperatur fehlgeschlagen. "
                            "Bitte die Zugangsdaten prüfen."
                        )
                        _LOGGER.debug("Anmeldung fehlgeschlagen: URL=%s, Benutzer=%s, Antwort=%s",
                                    endpoint, self._user, response_text)
                    else:
                        _LOGGER.error("Fehler beim Setzen der Temperatur: Status=%s, Antwort=%s",
                                    response.status, response_text)
                    return
                else:
                    _LOGGER.debug("Zieltemperatur erfolgreich gesetzt: %s", response_text)

                    # Lokalen Wert sofort setzen, damit die Oberfläche reagiert
                    self._attr_target_temperature = temperature
                    self.async_write_ha_state()

                    # Sofortige Aktualisierung der Daten anfordern, damit alle Entities aktuell sind
                    _LOGGER.debug("Aktualisierung der Daten wird nach der Temperaturänderung angefordert")
                    await self.coordinator.async_refresh()

        except Exception as ex:
            _LOGGER.exception("Ausnahme beim Setzen der Temperatur: %s", ex)
            return