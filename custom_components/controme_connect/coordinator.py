"""DataUpdateCoordinator der Controme-Integration."""
import asyncio
from datetime import timedelta
import logging
from typing import Any, Dict

from aiohttp import ClientTimeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, UPDATE_CHECK_INTERVAL
from .firmware import async_detect_houses, async_fetch_latest_version

_LOGGER = logging.getLogger(__name__)

# Der Mini-Server antwortet normalerweise in einer halben Sekunde. Manchmal
# arbeitet er aber (Weboberfläche, Optimierung der Heizkreise) und braucht
# deutlich länger. Mit zehn Sekunden gingen die Werte der Anlage dabei
# verloren, deshalb ist das Zeitlimit großzügiger.
REQUEST_TIMEOUT = ClientTimeout(total=20)

class ContromeDataUpdateCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Klasse zum Abrufen der Controme-Daten."""

    def __init__(
        self,
        hass: HomeAssistant,
        base_url: str,
        house_id: str,
        user: str = "",
        password: str = "",
    ) -> None:
        """Initialisiert den Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )
        self._base_url = base_url
        self._house_id = house_id
        self._user = user
        self._password = password
        self._update_check: dict[str, Any] = {
            "version": None,
            "lab_version": None,
            "page": None,
            "candidates": [],
            "available": None,
            "status": "nicht geprüft",
        }
        self._next_update_check = None
        self._update_task: asyncio.Task | None = None
        self._houses: list[str] | None = None

    async def _async_get_json(self, path: str) -> Any:
        """Ruft ein einzelnes JSON-Dokument von der Controme-API ab."""
        session = async_get_clientsession(self.hass)
        endpoint = f"{self._base_url}/get/json/v1/{self._house_id}/{path}"

        async with session.get(endpoint, timeout=REQUEST_TIMEOUT) as response:
            if response.status != 200:
                raise UpdateFailed(f"Fehler beim Abruf von {path}: {response.status}")
            return await response.json()

    async def _async_get_optional(self, path: str, parser) -> Dict[Any, Any]:
        """Ruft einen optionalen Endpunkt ab und verkraftet Fehler."""
        try:
            return parser(await self._async_get_json(path))
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warning("Optionaler Controme-Endpunkt %s ist nicht verfügbar: %s", path, ex)
            return {}

    @staticmethod
    def _parse_deviation(data: Any) -> Dict[int, Dict[str, Any]]:
        """Wandelt den Endpunkt der Abweichung in eine Zuordnung von Raum-IDs um."""
        result: Dict[int, Dict[str, Any]] = {}
        if not isinstance(data, list):
            return result
        for entry in data:
            if not isinstance(entry, dict):
                continue
            for room_id, values in entry.items():
                try:
                    result[int(room_id)] = values
                except (TypeError, ValueError):
                    continue
        return result

    @staticmethod
    def _parse_rooms(data: Any) -> Dict[int, str]:
        """Wandelt den Endpunkt der Räume in eine Zuordnung von Raum-ID zu Icon um."""
        result: Dict[int, str] = {}
        if not isinstance(data, list):
            return result
        for floor in data:
            if not isinstance(floor, dict):
                continue
            for room in floor.get("raeume", []):
                try:
                    result[int(room["id"])] = room.get("icon", "")
                except (KeyError, TypeError, ValueError):
                    continue
        return result

    async def _async_update_data(self) -> Dict[str, Any]:
        """Ruft die Daten von der Controme-API ab."""
        session = async_get_clientsession(self.hass)
        endpoint = f"{self._base_url}/get/json/v1/{self._house_id}/temps/"

        try:
            start_time = self.hass.loop.time()
            async with session.get(endpoint, timeout=REQUEST_TIMEOUT) as response:
                if response.status != 200:
                    raise UpdateFailed(f"Error fetching data: {response.status}")
                floors = await response.json()

            fetch_time = self.hass.loop.time() - start_time
            _LOGGER.debug(
                "Abruf der Controme-Daten in %.3f Sekunden abgeschlossen (erfolgreich: True)",
                fetch_time,
            )

            if floors and isinstance(floors, list) and len(floors) > 0:
                _LOGGER.debug("Daten für %d Etagen empfangen", len(floors))

            # Die zusätzlichen Endpunkte sind optional, ein fehlender darf die
            # Raumsensoren nicht beeinträchtigen.
            deviation = await self._async_get_optional("deviation/", self._parse_deviation)
            rooms = await self._async_get_optional("rooms/", self._parse_rooms)
            info = await self._async_get_optional("info/", self._parse_info)

            # Die Update-Prüfung läuft im Hintergrund, damit eine
            # langsame Weboberfläche die Raumsensoren nicht blockiert
            self._async_start_update_check()

            # Einmalig ermitteln, welche Haus-IDs die Anlage liefert
            if self._houses is None:
                self._houses = await self._async_detect_houses()
                if self._houses and self._house_id not in self._houses:
                    _LOGGER.warning(
                        "Die eingestellte Haus-ID %s gibt es in dieser Anlage nicht, "
                        "verfügbar sind: %s. Bitte unter Neu konfigurieren anpassen.",
                        self._house_id,
                        ", ".join(self._houses),
                    )

            return {
                "floors": floors,
                "deviation": deviation,
                "rooms": rooms,
                "info": info,
                "update": self._update_check,
                "houses": self._houses or [],
            }
        except Exception as ex:
            _LOGGER.error("Fehler bei der Kommunikation mit der API: %s", str(ex))
            raise UpdateFailed(f"Fehler bei der Kommunikation mit der API: {str(ex)}")

    @staticmethod
    def _parse_info(data: Any) -> Dict[str, Any]:
        """Gibt die Systeminformationen des Mini-Servers zurück."""
        return data if isinstance(data, dict) else {}

    async def _async_detect_houses(self) -> list[str]:
        """Gibt die Haus-IDs zurück, für die die Anlage Daten liefert."""
        try:
            return await async_detect_houses(
                self._base_url, self._user, self._password
            )
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warning("Die Controme-Häuser konnten nicht ermittelt werden: %s", ex)
            return []

    async def async_shutdown(self) -> None:
        """Beendet den Coordinator und seine Hintergrundaufgabe."""
        if self._update_task is not None and not self._update_task.done():
            self._update_task.cancel()
        await super().async_shutdown()

    def _async_start_update_check(self) -> None:
        """Startet die Prüfung auf Firmware-Updates im Hintergrund.

            Die Prüfung braucht einen Login an der Weboberfläche und
            erfolgt nur alle paar Stunden. Sie läuft als eigene Aufgabe, eine
            langsame oder nicht erreichbare Weboberfläche darf die
            Raumsensoren niemals blockieren oder fehlschlagen lassen.
        """
        now = dt_util.utcnow()
        if self._next_update_check is not None and now < self._next_update_check:
            return
        if self._update_task is not None and not self._update_task.done():
            return

        self._next_update_check = now + UPDATE_CHECK_INTERVAL
        self._update_task = self.hass.async_create_task(self._async_check_update())

    async def _async_check_update(self) -> None:
        """Prüft die Weboberfläche auf eine verfügbare Firmware-Version."""
        try:
            result = await async_fetch_latest_version(
                self._base_url, self._user, self._password, self._house_id
            )
        except asyncio.CancelledError:
            # Die Prüfung wurde beim Entladen abgebrochen, das ist kein Fehler
            raise
        except Exception as ex:  # pylint: disable=broad-except
            # Die Update-Prüfung darf die Raumsensoren nie beeinträchtigen
            _LOGGER.warning("Die Controme-Update-Prüfung ist fehlgeschlagen: %s", ex)
            result = {
                "version": None,
                "lab_version": None,
                "page": None,
                "candidates": [],
                "available": None,
                "status": f"Fehler bei der Prüfung: {ex}",
            }
        # In place, damit die bereits verteilten Daten aktualisiert werden
        self._update_check.update(result)
        _LOGGER.debug("Controme-Update-Prüfung: %s", self._update_check)
