"""DataUpdateCoordinator for Controme integration."""
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
REQUEST_TIMEOUT = ClientTimeout(total=10)

class ContromeDataUpdateCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Class to manage fetching Controme data."""

    def __init__(
        self,
        hass: HomeAssistant,
        base_url: str,
        house_id: str,
        user: str = "",
        password: str = "",
    ) -> None:
        """Initialize the coordinator."""
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
        """Fetch a single JSON document from the Controme API."""
        session = async_get_clientsession(self.hass)
        endpoint = f"{self._base_url}/get/json/v1/{self._house_id}/{path}"

        async with session.get(endpoint, timeout=REQUEST_TIMEOUT) as response:
            if response.status != 200:
                raise UpdateFailed(f"Error fetching {path}: {response.status}")
            return await response.json()

    async def _async_get_optional(self, path: str, parser) -> Dict[Any, Any]:
        """Fetch an optional endpoint and tolerate failures."""
        try:
            return parser(await self._async_get_json(path))
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warning("Optional Controme endpoint %s is unavailable: %s", path, ex)
            return {}

    @staticmethod
    def _parse_deviation(data: Any) -> Dict[int, Dict[str, Any]]:
        """Convert the deviation endpoint into a room id mapping."""
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
        """Convert the rooms endpoint into a room id to icon mapping."""
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
        """Fetch data from Controme API."""
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
                "Finished fetching controme data in %.3f seconds (success: True)",
                fetch_time,
            )

            if floors and isinstance(floors, list) and len(floors) > 0:
                _LOGGER.debug("Received data for %d floors", len(floors))

            # The additional endpoints are optional, a missing one must not
            # break the room sensors.
            deviation = await self._async_get_optional("deviation/", self._parse_deviation)
            rooms = await self._async_get_optional("rooms/", self._parse_rooms)
            info = await self._async_get_optional("info/", self._parse_info)

            # Die Update-Pruefung laeuft im Hintergrund, damit eine
            # langsame Weboberfuehrung die Raumsensoren nicht blockiert
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
            _LOGGER.error("Error communicating with API: %s", str(ex))
            raise UpdateFailed(f"Error communicating with API: {str(ex)}")

    @staticmethod
    def _parse_info(data: Any) -> Dict[str, Any]:
        """Return the system information of the mini server."""
        return data if isinstance(data, dict) else {}

    async def _async_detect_houses(self) -> list[str]:
        """Return the house ids the Controme system delivers data for."""
        try:
            return await async_detect_houses(
                self._base_url, self._user, self._password
            )
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warning("Could not determine the Controme houses: %s", ex)
            return []

    async def async_shutdown(self) -> None:
        """Shut down the coordinator and its background task."""
        if self._update_task is not None and not self._update_task.done():
            self._update_task.cancel()
        await super().async_shutdown()

    def _async_start_update_check(self) -> None:
        """Start the firmware update check in the background.

        The check needs a login to the web interface and is only done every
        few hours. It runs as a separate task, a slow or unreachable web
        interface must never block or fail the room sensors.
        """
        now = dt_util.utcnow()
        if self._next_update_check is not None and now < self._next_update_check:
            return
        if self._update_task is not None and not self._update_task.done():
            return

        self._next_update_check = now + UPDATE_CHECK_INTERVAL
        self._update_task = self.hass.async_create_task(self._async_check_update())

    async def _async_check_update(self) -> None:
        """Check the web interface for an available firmware version."""
        try:
            result = await async_fetch_latest_version(
                self._base_url, self._user, self._password, self._house_id
            )
        except asyncio.CancelledError:
            # Die Pruefung wurde beim Entladen abgebrochen, das ist kein Fehler
            raise
        except Exception as ex:  # pylint: disable=broad-except
            # The update check must never break the room sensors
            _LOGGER.warning("Controme update check failed: %s", ex)
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
        _LOGGER.debug("Controme update check: %s", self._update_check)
