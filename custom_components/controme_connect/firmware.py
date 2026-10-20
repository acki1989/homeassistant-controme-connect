"""Firmware update helpers for the Controme integration."""
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

# Tokens of the login form
CSRF_PATTERN = re.compile(r"name='csrfmiddlewaretoken'\s+value='([^']+)'")

# Title of a page
TITLE_PATTERN = re.compile(r"<title>([^<]*)</title>", re.IGNORECASE)

# Markers of a page that does not exist
ERROR_MARKERS = (
    "Seite konnte nicht gefunden werden",
    "Smart-Heat-OS - Fehler",
)

# Endpoints of the web interface that deliver the available versions. The
# stable version is the relevant one, the lab version is only a beta.
STABLE_VERSION_PATH = "/m_setup/{house_id}/hardware/setup_rpi/?vertarget=stable_v2&ms=2"
LAB_VERSION_PATH = "/m_setup/{house_id}/hardware/setup_rpi/?vertarget=lab_v2&ms=2"

# The web interface asks the server with this request whether a newer
# version is available: a successful answer means "update available", an
# error means that the installed version is the newest one.
UPDATE_AVAILABLE_PATH = "/m_setup/{house_id}/hardware/setup_rpi/?verdate=2"

# Page of the mini server with the software update section
MINISERVER_PATH = "/m_setup/{house_id}/hardware/setup_rpi/?create=2"

# System check of the web interface as JSON
OVERVIEW_PATH = "/m_setup/{house_id}/hardware/?overview=1"

# Controme names its versions with a date
VERSION_PATTERN = re.compile(
    r"\b(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}:\d{2}))?\b"
)

# The update section of the mini server page
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
    """Parse a Controme version into a comparable date.

    The mini server reports the installed build in ISO format, the web
    interface uses the German date format for the available version.
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
    """Return all string values of a JSON document."""
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
    """Return the version of a short answer of the web interface."""
    text = (text or "").strip()
    if text.startswith("{") or text.startswith("["):
        try:
            data = json.loads(text)
        except ValueError:
            data = None
        if data is not None:
            # The stable version is the relevant one
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
    """Extract the software update section of the mini server page."""
    section: dict[str, str] = {}
    for key, pattern in UPDATE_SECTION_PATTERNS.items():
        match = pattern.search(html)
        if match:
            section[key] = re.sub(r"\s+", " ", match.group(1)).strip()
    return section


def parse_overview(data: Any) -> list[dict[str, Any]]:
    """Convert the system check of the web interface into a readable list."""
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
    """Log in to the Controme web interface."""
    login_url = f"{base_url}{LOGIN_PATH}"
    try:
        async with session.get(login_url) as response:
            html = await response.text()
    except aiohttp.ClientError as err:
        _LOGGER.debug("Controme login page not reachable: %s", err)
        return False, f"Anmeldeseite nicht erreichbar: {err}"

    match = CSRF_PATTERN.search(html)
    if not match:
        _LOGGER.debug("No login token found on the Controme login page")
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
        _LOGGER.debug("Controme login failed: %s", err)
        return False, f"Anmeldung fehlgeschlagen: {err}"


async def _async_fetch_page(session, url: str) -> tuple[str | None, str]:
    """Fetch a page of the web interface.

    Returns the content and a short description of the response. The content
    is None if the page does not exist.
    """
    try:
        async with session.get(url) as response:
            status = response.status
            if status != 200:
                return None, f"HTTP {status}"
            body = await response.text()
    except aiohttp.ClientError as err:
        _LOGGER.debug("Controme page %s not reachable: %s", url, err)
        return None, f"Fehler: {err}"

    if any(marker in body for marker in ERROR_MARKERS):
        return None, "Fehlerseite"
    title = TITLE_PATTERN.search(body)
    return body, f"HTTP 200 ({title.group(1).strip() if title else 'ohne Titel'})"


async def _async_has_update(session, url: str) -> tuple[bool | None, str]:
    """Ask the mini server whether a newer version is available.

    The web interface uses the same request: a successful answer means that
    an update is offered, an error means that the installed version is the
    newest one. The error page of the web interface is answered with status
    200, so the content has to be checked as well.
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
        _LOGGER.debug("Controme update query failed: %s", err)
        return None, f"Fehler: {err}"


async def async_check_credentials(
    base_url: str, user: str, password: str
) -> tuple[bool, str]:
    """Check the access data with a login to the web interface.

    The data endpoints of the API answer every request, also with a wrong
    password. Only the web interface checks the access data, so it is used to
    validate them.
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
    """Return the house ids the Controme system provides a web interface for.

    The data endpoints of the API answer for every house id, so they cannot be
    used to tell the houses apart. The web interface however is bound to a
    house, it only exists for the houses that are actually configured. One
    login is enough for the query of all ids.
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
                        "Could not log in to the Controme web interface, "
                        "the houses cannot be determined"
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
        _LOGGER.warning("Could not determine the Controme houses: %s", err)
        return []
    return houses


async def _async_fetch_version(
    session, base_url: str, house_id: str, path: str, attempts: list[str]
) -> str | None:
    """Return the version that the web interface offers for a branch."""
    url = f"{base_url}{path.format(house_id=house_id)}"
    body, info = await _async_fetch_page(session, url)
    attempts.append(f"{path.format(house_id=house_id)} -> {info}")
    if body is None:
        return None
    return extract_short_version(body)


async def async_fetch_latest_version(
    base_url: str, user: str, password: str, house_id: str = "1"
) -> dict[str, Any]:
    """Check the Controme web interface for an available firmware version.

    The API of the mini server does not expose the update state, only the web
    interface does. Returns a dictionary with the available version, the
    information about the installed software and a status message.
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

    # Cookies of an IP address are only accepted with an unsafe cookie jar
    jar = aiohttp.CookieJar(unsafe=True)
    async with aiohttp.ClientSession(cookie_jar=jar, timeout=REQUEST_TIMEOUT) as session:
        logged_in, login_status = await _async_login(session, base_url, user, password)
        if not logged_in:
            result["status"] = login_status
            return result

        # The available version is delivered by the mini server page. The
        # server sometimes needs a second attempt, for example directly
        # after the login.
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

        # The lab version is a beta and is only reported for information
        result["lab_version"] = await _async_fetch_version(
            session, base_url, house_id, LAB_VERSION_PATH, attempts
        )

        # Ask the server whether a newer version is offered
        url = f"{base_url}{UPDATE_AVAILABLE_PATH.format(house_id=house_id)}"
        available, info = await _async_has_update(session, url)
        attempts.append(f"{UPDATE_AVAILABLE_PATH.format(house_id=house_id)} -> {info}")
        result["available"] = available

        # Information about the installed software and the system check
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
