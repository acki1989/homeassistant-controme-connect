"""Konfigurationsablauf der Controme-Integration."""
import logging
from typing import Any, Optional

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, CONF_API_URL, CONF_HAUS_ID, CONF_USER, CONF_PASSWORD
from .firmware import async_check_credentials, async_detect_houses
from .helpers import scan_network

_LOGGER = logging.getLogger(__name__)

# Zeitlimit für den Verbindungstest zur API
CONNECT_TIMEOUT = 10


def normalize_url(url: str) -> str:
    """Gibt die API-URL mit Schema und ohne abschließenden Slash zurück."""
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    return url.rstrip("/")


class ContromeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Verarbeitet einen Konfigurationsablauf für Controme."""

    VERSION = 1

    def __init__(self):
        """Initialisiert den Konfigurationsablauf."""
        self._discovered_systems = []
        self._user_input = {}
        self._scan_already_run = False
        self._houses: list[str] = []

    async def async_step_user(self, user_input: Optional[dict[str, Any]] = None) -> FlowResult:
        """Verarbeitet den ersten Schritt."""
        if user_input is None:
            # Suchmerkmal beim Start eines neuen Ablaufs zurücksetzen
            self._scan_already_run = False
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("discovery_method"): vol.In(
                            {
                                "auto": "Automatisch nach Controme-Systemen im Netzwerk suchen",
                                "manual": "IP-Adresse und Zugangsdaten manuell eingeben",
                            }
                        )
                    }
                ),
            )

        if "discovery_method" in user_input:
            if user_input["discovery_method"] == "auto":
                return await self.async_step_auto_discovery()
            return await self.async_step_manual_entry()

        return self.async_abort(reason="unknown")

    async def async_step_auto_discovery(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Verarbeitet den Schritt der automatischen Ermittlung."""
        if user_input is None:
            # Suchmerkmal beim Start eines neuen Ablaufs zurücksetzen
            if not self._scan_already_run:
                self._scan_already_run = True
                await self._async_scan_systems()
            return self._show_form_after_scan()

        return await self.async_step_user(user_input)

    async def _async_scan_systems(self) -> None:
        """Durchsucht das Netzwerk nach Controme-Systemen."""
        try:
            _LOGGER.info("Das Netzwerk wird nach Controme-Systemen durchsucht ...")
            self._discovered_systems = await scan_network()
            _LOGGER.info("Netzwerksuche abgeschlossen. %d Systeme gefunden", len(self._discovered_systems))
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Fehler bei der Netzwerksuche: %s", err)
            self._discovered_systems = []

    def _show_form_after_scan(self) -> FlowResult:
        """Zeigt das Formular nach der Netzwerksuche."""
        if self._discovered_systems:
            if len(self._discovered_systems) == 1:
                system = self._discovered_systems[0]
                return self.async_show_form(
                    step_id="credentials",
                    description_placeholders={"system": system["title"]},
                    data_schema=vol.Schema(
                        {
                            vol.Required(CONF_USER): str,
                            vol.Required(CONF_PASSWORD): str,
                        }
                    ),
                )

            return self.async_show_form(
                step_id="select_system",
                description_placeholders={"count": len(self._discovered_systems)},
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_API_URL): vol.In(
                            {
                                system["url"]: system["title"]
                                for system in self._discovered_systems
                            }
                        ),
                        vol.Required(CONF_USER): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
            )

        _LOGGER.warning("Bei der Suche wurden keine Controme-Systeme gefunden. Es folgt die manuelle Eingabe.")
        return self.async_show_form(
            step_id="manual_entry",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_URL): str,
                    vol.Required(CONF_USER): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors={},
        )

    async def async_step_credentials(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Lässt die Zugangsdaten eingeben und prüft sie."""
        errors = {}

        if user_input is not None and self._discovered_systems:
            self._user_input = {
                CONF_API_URL: normalize_url(self._discovered_systems[0]["url"]),
                CONF_USER: user_input[CONF_USER],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            error = await self._async_check_access_data()
            if error is None:
                return await self._async_select_house()
            errors["base"] = error

        system = self._discovered_systems[0] if self._discovered_systems else {"title": "Controme"}
        return self.async_show_form(
            step_id="credentials",
            description_placeholders={"system": system["title"]},
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_USER): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
                user_input or {},
            ),
            errors=errors,
        )

    async def async_step_manual_entry(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Verarbeitet den Schritt der manuellen Eingabe."""
        errors = {}

        if user_input is not None:
            self._user_input = {
                CONF_API_URL: normalize_url(user_input[CONF_API_URL]),
                CONF_USER: user_input[CONF_USER],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            error = await self._async_check_access_data()
            if error is None:
                return await self._async_select_house()
            errors["base"] = error

        return self.async_show_form(
            step_id="manual_entry",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_API_URL): str,
                        vol.Required(CONF_USER): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
                user_input or {},
            ),
            errors=errors,
        )

    async def async_step_select_system(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Verarbeitet den Schritt der Systemauswahl."""
        if user_input is not None:
            self._user_input = {
                CONF_API_URL: normalize_url(user_input[CONF_API_URL]),
                CONF_USER: user_input[CONF_USER],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            error = await self._async_check_access_data()
            if error is None:
                return await self._async_select_house()
            return self.async_show_form(
                step_id="select_system",
                description_placeholders={"count": len(self._discovered_systems)},
                data_schema=self.add_suggested_values_to_schema(
                    vol.Schema(
                        {
                            vol.Required(CONF_API_URL): vol.In(
                                {
                                    system["url"]: system["title"]
                                    for system in self._discovered_systems
                                }
                            ),
                            vol.Required(CONF_USER): str,
                            vol.Required(CONF_PASSWORD): str,
                        }
                    ),
                    user_input or {},
                ),
                errors={"base": error},
            )

        return await self.async_step_user(user_input)

    async def _async_check_access_data(self) -> Optional[str]:
        """Prüft die API und die Zugangsdaten.

            Gibt einen Fehlschlüssel zurück oder None, wenn alles stimmt. Die
            Zugangsdaten werden nur beim Login an der Weboberfläche geprüft,
            die Daten-Endpunkte der API antworten auf jede Anfrage.
        """
        base_url = normalize_url(self._user_input[CONF_API_URL])

        # Die API muss antworten
        try:
            url = f"{base_url}/get/json/v1/1/rooms/"
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=CONNECT_TIMEOUT)
            ) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return "cannot_connect"
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Die Controme-API ist nicht erreichbar: %s", err)
            return "cannot_connect"

        # Die Zugangsdaten werden nur beim Login an der Weboberfläche geprüft
        logged_in, status = await async_check_credentials(
            base_url, self._user_input[CONF_USER], self._user_input[CONF_PASSWORD]
        )
        if not logged_in:
            _LOGGER.warning("Anmeldung an der Controme-Weboberfläche fehlgeschlagen: %s", status)
            return "invalid_auth"
        return None

    async def _async_select_house(self) -> FlowResult:
        """Ermittelt die Häuser und lässt den Nutzer eines auswählen."""
        self._houses = await async_detect_houses(
            self._user_input[CONF_API_URL],
            self._user_input[CONF_USER],
            self._user_input[CONF_PASSWORD],
        )
        _LOGGER.info("Gefundene Controme-Häuser: %s", self._houses)

        if len(self._houses) == 1:
            self._user_input[CONF_HAUS_ID] = self._houses[0]
            return self._async_create_entry()
        return await self.async_step_select_house()

    async def async_step_select_house(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Lässt den Nutzer das Haus auswählen."""
        if user_input is not None:
            self._user_input[CONF_HAUS_ID] = user_input[CONF_HAUS_ID]
            return self._async_create_entry()

        if self._houses:
            data_schema = vol.Schema(
                {
                    vol.Required(CONF_HAUS_ID): vol.In(
                        {house_id: f"Haus {house_id}" for house_id in self._houses}
                    )
                }
            )
        else:
            # Die Häuser konnten nicht ermittelt werden, die ID wird von Hand
            # eingetragen
            data_schema = vol.Schema({vol.Required(CONF_HAUS_ID, default="1"): str})
        return self.async_show_form(step_id="select_house", data_schema=data_schema, errors={})

    def _async_create_entry(self) -> FlowResult:
        """Erstellt den Konfigurationseintrag."""
        return self.async_create_entry(
            title="Controme Connect",
            data={
                CONF_API_URL: normalize_url(self._user_input[CONF_API_URL]),
                CONF_USER: self._user_input[CONF_USER],
                CONF_PASSWORD: self._user_input[CONF_PASSWORD],
                CONF_HAUS_ID: self._user_input.get(CONF_HAUS_ID, "1"),
            },
        )

    async def async_step_reconfigure(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Erlaubt das Ändern der Einstellungen der Integration."""
        entry = self._get_reconfigure_entry()
        errors = {}

        if user_input is not None:
            data = {
                CONF_API_URL: normalize_url(user_input[CONF_API_URL]),
                CONF_HAUS_ID: str(user_input[CONF_HAUS_ID]).strip(),
                CONF_USER: user_input[CONF_USER],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }

            self._user_input = {
                CONF_API_URL: data[CONF_API_URL],
                CONF_USER: data[CONF_USER],
                CONF_PASSWORD: data[CONF_PASSWORD],
            }
            error = await self._async_check_access_data()
            if error is None:
                old_house = entry.data.get(CONF_HAUS_ID)
                if data[CONF_HAUS_ID] != old_house:
                    # Die bisherigen Entities gehören zur alten Haus-ID und
                    # würden ohne Bereinigung als Leichen zurückbleiben
                    self._async_remove_old_entities(entry)
                return self.async_update_reload_and_abort(entry, data=data)
            errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_URL, default=entry.data.get(CONF_API_URL)
                    ): str,
                    vol.Required(
                        CONF_HAUS_ID, default=entry.data.get(CONF_HAUS_ID)
                    ): str,
                    vol.Required(
                        CONF_USER, default=entry.data.get(CONF_USER)
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=entry.data.get(CONF_PASSWORD)
                    ): str,
                }
            ),
            errors=errors,
        )

    @callback
    def _async_remove_old_entities(self, entry: config_entries.ConfigEntry) -> None:
        """Entfernt die Entities und Geräte der Integration aus dem Registry."""
        registry = er.async_get(self.hass)
        for reg_entry in list(er.async_entries_for_config_entry(registry, entry.entry_id)):
            _LOGGER.info("Entity %s des vorherigen Hauses wird entfernt", reg_entry.entity_id)
            registry.async_remove(reg_entry.entity_id)
        # Ohne die Geräte bleiben die Waisen des vorherigen Hauses stehen
        device_registry = dr.async_get(self.hass)
        for device in list(dr.async_entries_for_config_entry(device_registry, entry.entry_id)):
            _LOGGER.info("Gerät %s des vorherigen Hauses wird entfernt", device.name)
            device_registry.async_remove_device(device.id)

    # Home Assistant mitteilen, wie der Fortschrittsschritt zu behandeln ist
    @staticmethod
    def async_get_progress_steps() -> list[str]:
        """Gibt die Fortschrittsschritte des Ablaufs zurück."""
        return ["auto_discovery"]
