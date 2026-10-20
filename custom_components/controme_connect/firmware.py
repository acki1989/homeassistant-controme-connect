"""Hilfsfunktionen für Firmware-Updates der Controme-Integration."""
import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any

import aiohttp

from .const import HOUSE_ID_CHECK_COUNT

_LOGGER = logging.getLogger(__name__)

LOGIN_PATH = "/accounts/m_login/"

# Token des Anmeldeformulars
CSRF_PATTERN = re.compile(r"name='csrfmiddlewaretoken'\s+value='([^']+)'")

# Titel einer Seite
TITLE_PATTERN = re.compile(r"<title>([^<]*)</title>", re.IGNORECASE)

# Merkmale einer Seite, die es nicht gibt
ERROR_MARKERS = (
    "Seite konnte nicht gefunden werden",
    "Smart-Heat-OS - Fehler",
)

# Endpunkte der Weboberfläche, die die verfügbaren Versionen liefern. Die
# stabile Version ist die maßgebliche, die Lab-Version ist nur eine Beta.
STABLE_VERSION_PATH = "/m_setup/{house_id}/hardware/setup_rpi/?vertarget=stable_v2&ms=2"
LAB_VERSION_PATH = "/m_setup/{house_id}/hardware/setup_rpi/?vertarget=lab_v2&ms=2"

# Mit dieser Anfrage fragt die Weboberfläche den Server, ob eine neuere
# Version verfügbar ist: eine erfolgreiche Antwort bedeutet "Update verfügbar",
# ein Fehler bedeutet, dass die installierte Version die neueste ist.
UPDATE_AVAILABLE_PATH = "/m_setup/{house_id}/hardware/setup_rpi/?verdate=2"

# Seite des Mini-Servers mit dem Abschnitt zur Softwareaktualisierung
MINISERVER_PATH = "/m_setup/{house_id}/hardware/setup_rpi/?create=2"

# Systemcheck der Weboberfläche als JSON
OVERVIEW_PATH = "/m_setup/{house_id}/hardware/?overview=1"

# Controme bezeichnet seine Versionen mit einem Datum
VERSION_PATTERN = re.compile(
    r"\b(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}:\d{2}))?\b"
)

# Abschnitt zur Aktualisierung auf der Mini-Server-Seite
UPDATE_SECTION_PATTERNS = {
    "installed_branch": re.compile(
        r"Installierte Softwareversion:?\s*([^<\n]{0,40})", re.IGNORECASE
    ),
    "installed_build": re.compile(
        r"Softwarestand von:?\s*([^<\n]{0,40})", re.IGNORECASE
    ),
    "uptime_since": re.compile(r"an seit\s*([^<\n]{0,40})", re.IGNORECASE),
    "system_time": re.compile(
        r"Aktuelle Systemzeit:?\s*([^<\n]{0,40})", re.IGNORECASE
    ),
    "miniserver": re.compile(
        r"Miniserver-Version:?\s*([^<\n]{0,60})", re.IGNORECASE
    ),
}

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


def parse_version(value: str) -> datetime | None:
    """Wandelt eine Controme-Version in ein vergleichbares Datum um.

        Der Mini-Server meldet den installierten Build im ISO-Format, die
        Weboberfläche verwendet für die verfügbare Version das deutsche
        Datumsformat.
    """
    if not value:
        return None
    for version_format in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
    ):
        try:
            return datetime.strptime(value.strip(), version_format)
        except ValueError:
            continue
    return None


def _flatten(data: Any) -> list[str]:
    """Gibt alle Textwerte eines JSON-Dokuments zurück."""
    values: list[str] = []
    if isinstance(data, dict):
        for value in data.values():
            values.extend(_flatten(value))
    elif isinstance(data, list):
        for value in data:
            values.extend(_flatten(value))
    elif data is not None:
        values.append(str(data))
    return values


def extract_short_version(text: str) -> str | None:
    """Gibt die Version aus der kurzen Antwort der Weboberfläche zurück."""
    text = (text or "").strip()
    if text.startswith("{") or text.startswith("["):
        try:
            data = json.loads(text)
        except ValueError:
            data = None
        if data is not None:
            # Die stabile Version ist die maßgebliche
            if isinstance(data, dict):
                for key, value in data.items():
                    if "stable" in str(key).lower() and not "lab" in str(key).lower():
                        version = extract_short_version(str(value))
                        if version:
                            return version
            for value in _flatten(data):
                version = extract_short_version(value)
                if version:
                    return version
            return None

    match = VERSION_PATTERN.search(text)
    if match:
        return match.group(0)
    return None


def parse_update_section(html: str) -> dict[str, str]:
    """Extrahiert den Abschnitt zur Softwareaktualisierung der Mini-Server-Seite."""
    section: dict[str, str] = {}
    for key, pattern in UPDATE_SECTION_PATTERNS.items():
        match = pattern.search(html)
        if match:
            section[key] = re.sub(r"\s+", " ", match.group(1)).strip()
    return section


def parse_overview(data: Any) -> list[dict[str, Any]]:
    """Wandelt den Systemcheck der Weboberfläche in eine lesbare Liste um."""
    overview: list[dict[str, Any]] = []
    if not isinstance(data, list):
        return overview

    for section in data:
        if not isinstance(section, dict):
            continue
        texts: list[str] = []
        for row in section.get("text", []) or []:
            if isinstance(row, list) and row:
                texts.append(str(row[-1]))
        overview.append(
            {
                "heading": section.get("heading", ""),
                "status": section.get("status", ""),
                "text": texts,
            }
        )
    return overview


async def _async_login(session, base_url: str, user: str, password: str) -> tuple[bool, str]:
    """Meldet sich an der Controme-Weboberfläche an."""
    login_url = f"{base_url}{LOGIN_PATH}"
    try:
        async with session.get(login_url) as response:
            html = await response.text()
    except aiohttp.ClientError as err:
        _LOGGER.debug("Anmeldeseite von Controme nicht erreichbar: %s", err)
        return False, f"Anmeldeseite nicht erreichbar: {err}"

    match = CSRF_PATTERN.search(html)
    if not match:
        _LOGGER.debug("Auf der Controme-Anmeldeseite wurde kein Login-Token gefunden")
        return False, "Kein Anmelde-Token auf der Anmeldeseite gefunden"

    data = {
        "mail": user,
        "pw": password,
        "csrfmiddlewaretoken": match.group(1),
    }
    try:
        async with session.post(
            login_url,
            data=data,
            headers={"Referer": login_url},
            allow_redirects=False,
        ) as response:
            if response.status in (301, 302):
                return True, "Anmeldung erfolgreich"
            body = await response.text()
            if "ungültig" in body or "ung&uuml;tig" in body:
                return False, "Benutzername oder Passwort ungültig"
            return False, f"Anmeldung fehlgeschlagen (HTTP {response.status})"
    except aiohttp.ClientError as err:
        _LOGGER.debug("Anmeldung an der Controme-Weboberfläche fehlgeschlagen: %s", err)
        return False, f"Anmeldung fehlgeschlagen: {err}"


async def _async_fetch_page(session, url: str) -> tuple[str | None, str]:
    """Ruft eine Seite der Weboberfläche ab.

        Gibt den Inhalt und eine kurze Beschreibung der Antwort zurück. Der
        Inhalt ist None, wenn es die Seite nicht gibt.
    """
    try:
        async with session.get(url) as response:
            status = response.status
            if status != 200:
                return None, f"HTTP {status}"
            body = await response.text()
    except aiohttp.ClientError as err:
        _LOGGER.debug("Controme-Seite %s nicht erreichbar: %s", url, err)
        return None, f"Fehler: {err}"

    if any(marker in body for marker in ERROR_MARKERS):
        return None, "Fehlerseite"
    title = TITLE_PATTERN.search(body)
    return body, f"HTTP 200 ({title.group(1).strip() if title else 'ohne Titel'})"


async def _async_has_update(session, url: str) -> tuple[bool | None, str]:
    """Fragt den Mini-Server, ob eine neuere Version verfügbar ist.

        Die Weboberfläche nutzt dieselbe Anfrage: eine erfolgreiche Antwort
        bedeutet, dass ein Update angeboten wird, ein Fehler bedeutet, dass
        die installierte Version die neueste ist. Die Fehlerseite der
        Weboberfläche wird mit Status 200 beantwortet, deshalb muss zusätzlich
        der Inhalt geprüft werden.
    """
    try:
        async with session.get(url) as response:
            status = response.status
            if status != 200:
                return False, f"HTTP {status}"
            body = await response.text()
            if any(marker in body for marker in ERROR_MARKERS):
                return False, f"HTTP 200 ({body.strip()[:60]})"
            if not body.strip():
                return None, "HTTP 200 (leere Antwort)"
            return True, f"HTTP 200 ({body.strip()[:60]})"
    except aiohttp.ClientError as err:
        _LOGGER.debug("Abfrage des Controme-Updates fehlgeschlagen: %s", err)
        return None, f"Fehler: {err}"


async def async_check_credentials(
    base_url: str, user: str, password: str
) -> tuple[bool, str]:
    """Prüft die Zugangsdaten mit einem Login an der Weboberfläche.

        Die Daten-Endpunkte der API antworten auf jede Anfrage, auch mit
        einem falschen Passwort. Nur die Weboberfläche prüft die Zugangsdaten,
        deshalb wird sie zur Validierung verwendet.
    """
    jar = aiohttp.CookieJar(unsafe=True)
    try:
        async with aiohttp.ClientSession(
            cookie_jar=jar, timeout=REQUEST_TIMEOUT
        ) as session:
            return await _async_login(session, base_url, user, password)
    except aiohttp.ClientError as err:
        return False, f"Die Controme-Weboberfläche ist nicht erreichbar: {err}"


async def async_detect_houses(
    base_url: str, user: str = "", password: str = ""
) -> list[str]:
    """Gibt die Haus-IDs zurück, für die die Anlage eine Weboberfläche hält.

        Die Daten-Endpunkte der API antworten für jede Haus-ID, sie können
        die Häuser also nicht unterscheiden. Die Weboberfläche ist dagegen an
        ein Haus gebunden, sie existiert nur für die tatsächlich eingerichteten
        Häuser. Eine Anmeldung genügt für die Abfrage aller IDs.
    """
    jar = aiohttp.CookieJar(unsafe=True)
    houses: list[str] = []
    try:
        async with aiohttp.ClientSession(
            cookie_jar=jar, timeout=REQUEST_TIMEOUT
        ) as session:
            if user and password:
                logged_in, _ = await _async_login(session, base_url, user, password)
                if not logged_in:
                    _LOGGER.warning(
                        "Anmeldung an der Controme-Weboberfläche fehlgeschlagen, "
                        "die Häuser können nicht ermittelt werden"
                    )
                    return []
            for house_id in range(1, HOUSE_ID_CHECK_COUNT + 1):
                url = (
                    f"{base_url.rstrip('/')}/m_setup/{house_id}"
                    "/hardware/setup_rpi/?create=2"
                )
                body, _ = await _async_fetch_page(session, url)
                if body is not None:
                    houses.append(str(house_id))
    except aiohttp.ClientError as err:
        _LOGGER.warning("Die Controme-Häuser konnten nicht ermittelt werden: %s", err)
        return []
    return houses


async def _async_fetch_version(
    session, base_url: str, house_id: str, path: str, attempts: list[str]
) -> str | None:
    """Gibt die Version zurück, die die Weboberfläche für einen Branch anbietet."""
    url = f"{base_url}{path.format(house_id=house_id)}"
    body, info = await _async_fetch_page(session, url)
    attempts.append(f"{path.format(house_id=house_id)} -> {info}")
    if body is None:
        return None
    return extract_short_version(body)


async def async_fetch_latest_version(
    base_url: str, user: str, password: str, house_id: str = "1"
) -> dict[str, Any]:
    """Prüft die Controme-Weboberfläche auf eine verfügbare Firmware-Version.

        Die API des Mini-Servers nennt den Update-Stand nicht, nur die
        Weboberfläche. Gibt ein Dictionary mit der verfügbaren Version, den
        Informationen zur installierten Software und einer Statusmeldung
        zurück.
    """
    attempts: list[str] = []
    result: dict[str, Any] = {
        "version": None,
        "page": None,
        "attempts": attempts,
        "versions": {},
        "available": None,
        "update_section": {},
        "overview": [],
        "status": "nicht geprüft",
    }

    # Cookies einer IP-Adresse werden nur mit einem unsicheren Cookie-Speicher akzeptiert
    jar = aiohttp.CookieJar(unsafe=True)
    async with aiohttp.ClientSession(cookie_jar=jar, timeout=REQUEST_TIMEOUT) as session:
        logged_in, login_status = await _async_login(session, base_url, user, password)
        if not logged_in:
            result["status"] = login_status
            return result

        # Die verfügbare Version liefert die Mini-Server-Seite. Der
        # Server braucht manchmal einen zweiten Versuch, zum Beispiel direkt
        # nach der Anmeldung.
        stable = await _async_fetch_version(
            session, base_url, house_id, STABLE_VERSION_PATH, attempts
        )
        if stable is None:
            await asyncio.sleep(2)
            stable = await _async_fetch_version(
                session, base_url, house_id, STABLE_VERSION_PATH, attempts
            )
        result["version"] = stable
        if stable:
            result["page"] = STABLE_VERSION_PATH.format(house_id=house_id)
            result["status"] = f"Verfügbare Version von {result['page']} abgerufen"

        # Die Lab-Version ist eine Beta und wird nur zur Information gemeldet
        result["lab_version"] = await _async_fetch_version(
            session, base_url, house_id, LAB_VERSION_PATH, attempts
        )

        # Den Server fragen, ob eine neuere Version angeboten wird
        url = f"{base_url}{UPDATE_AVAILABLE_PATH.format(house_id=house_id)}"
        available, info = await _async_has_update(session, url)
        attempts.append(f"{UPDATE_AVAILABLE_PATH.format(house_id=house_id)} -> {info}")
        result["available"] = available

        # Informationen zur installierten Software und zum Systemcheck
        url = f"{base_url}{MINISERVER_PATH.format(house_id=house_id)}"
        body, info = await _async_fetch_page(session, url)
        attempts.append(f"{MINISERVER_PATH.format(house_id=house_id)} -> {info}")
        if body is not None:
            result["update_section"] = parse_update_section(body)

        url = f"{base_url}{OVERVIEW_PATH.format(house_id=house_id)}"
        body, info = await _async_fetch_page(session, url)
        attempts.append(f"{OVERVIEW_PATH.format(house_id=house_id)} -> {info}")
        if body is not None:
            try:
                result["overview"] = parse_overview(json.loads(body))
            except ValueError:
                result["overview"] = []

        if not result["version"]:
            result["status"] = f"{login_status}; keine verfügbare Version gefunden"

    return result
