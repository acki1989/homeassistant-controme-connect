"""Hilfsfunktionen der Controme-Integration."""
import asyncio
import logging
import re
import unicodedata
from typing import List, Dict, Any, Optional, Set
import socket
import aiohttp
import async_timeout
from ipaddress import IPv4Network, IPv4Address, IPv4Interface

from .const import DEFAULT_ROOM_ICON, ROOM_ICONS

_LOGGER = logging.getLogger(__name__)


def room_icon(controme_icon: str) -> str:
    """Gibt das Material-Design-Icon zu einem Controme-Raum-Icon zurück."""
    return ROOM_ICONS.get(controme_icon, DEFAULT_ROOM_ICON)


def room_slug(room_name: str) -> str:
    """Gibt den Slug eines Raumnamens zurück, wie Home Assistant ihn erzeugt.

        Die Raumnamen der Controme-Anlage enden mit einem Leerzeichen, das
        würde in der Entity-ID zu einem doppelten Unterstrich führen.
    """
    text = unicodedata.normalize("NFKD", room_name or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def extract_humidity(room_data: Any) -> tuple[float | None, str | None]:
    """Gibt die Luftfeuchte eines Raums und die Quelle des Werts zurück.

        Auf Raumabene enthält die API nur den Wert eines im Raum
        verbauten Feuchtesensors. Multi-Sensoren liefern die Luftfeuchte als
        Teil ihres Sensorwerts, dieser wird als Rückfalloption verwendet.
    """
    try:
        return float(room_data.get("luftfeuchte")), "room"
    except (TypeError, ValueError):
        pass  # The value is not a number, the multi sensor is used instead

    for sensor in room_data.get("sensoren", []):
        sensor_value = sensor.get("wert")
        if not isinstance(sensor_value, dict):
            continue
        try:
            humidity = float(sensor_value.get("Relative Luftfeuchte"))
        except (TypeError, ValueError):
            continue
        return humidity, sensor.get("beschreibung") or sensor.get("name")

    return None, None


def extract_multi_sensor_values(room_data: Any) -> dict[str, Any]:
    """Gibt die zusätzlichen Werte der Multi-Sensoren eines Raums zurück.

        Je nach Sensor sind das Helligkeit und Bewegung, sie sind nur
        vorhanden, wenn der Sensor sie liefert.
    """
    values: dict[str, Any] = {}
    for sensor in room_data.get("sensoren", []):
        sensor_value = sensor.get("wert")
        if not isinstance(sensor_value, dict):
            continue
        for key, value in sensor_value.items():
            if key in ("Temperatur", "Relative Luftfeuchte") or value is None:
                continue
            values[key] = value
    return values

def get_local_ip() -> Optional[str]:
    """Ermittelt die lokale IP-Adresse des Rechners."""
    try:
        # Socket erzeugen und mit einer bekannten öffentlichen Adresse verbinden
        # Es wird keine echte Verbindung aufgebaut, aber die lokale IP wird ermittelt
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        local_ip = sock.getsockname()[0]
        sock.close()
        _LOGGER.debug("Lokale IP-Adresse erkannt: %s", local_ip)
        return local_ip
    except Exception as err:
        _LOGGER.error("Fehler beim Ermitteln der lokalen IP-Adresse: %s", err)
        return None

def get_network_from_ip(ip: str) -> Optional[str]:
    """Ermittelt das Netzwerk zu einer IP-Adresse."""
    try:
        # Ein /24-Netzwerk annehmen
        interface = IPv4Interface(f"{ip}/24")
        network_str = str(interface.network)
        _LOGGER.debug("Netzwerk aus der IP-Adresse %s ermittelt: %s", ip, network_str)
        return network_str
    except Exception as err:
        _LOGGER.error("Fehler beim Ermitteln des Netzwerks aus der IP-Adresse %s: %s", ip, err)
        return None

async def test_controme_host(session: aiohttp.ClientSession, ip: str) -> Optional[Dict[str, str]]:
    """Prüft anhand der Anmeldeseite, ob die IP ein Controme-System ist."""
    # Nur die URL der Anmeldeseite prüfen
    login_url = f"http://{ip}/accounts/m_login/"

    try:
        # Anmeldeseite mit kurzem Zeitlimit prüfen
        async with async_timeout.timeout(1):
            async with session.get(login_url) as response:
                if response.status == 200:
                    # Im HTML nach dem bestimmten Titel suchen
                    text = await response.text()
                    if "<title>Smart-Heat-OS - Login</title>" in text:
                        _LOGGER.info("Controme-System unter %s gefunden", ip)
                        return {"url": ip, "title": f"Controme at {ip}"}
    except Exception:  # pylint: disable=broad-except
        # Fehler übergehen
        pass

    return None

async def scan_network(networks: List[str] = None) -> List[Dict[str, str]]:
    """Durchsucht das Netzwerk nach Controme-Systemen und stoppt nach dem ersten."""
    start_time = asyncio.get_event_loop().time()

    if networks is None:
        # Lokales Netzwerk aus der IP von Home Assistant ermitteln
        local_ip = get_local_ip()
        if local_ip:
            network = get_network_from_ip(local_ip)
            if network:
                _LOGGER.info("Lokales Netzwerk erkannt: %s", network)
                networks = [network]
            else:
                _LOGGER.warning("Lokales Netzwerk konnte nicht ermittelt werden, es werden die Standardnetzwerke genutzt")
                networks = ["192.168.1.0/24"]
        else:
            _LOGGER.warning("Lokale IP-Adresse konnte nicht ermittelt werden, es werden die Standardnetzwerke genutzt")
            networks = ["192.168.1.0/24"]

    # Verbindungseinstellungen für ein schnelleres Suchen optimieren
    connector = aiohttp.TCPConnector(limit_per_host=10, limit=100)
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        for network in networks:
            _LOGGER.info("Netzwerk %s wird nach Controme-Systemen durchsucht", network)

            try:
                # Eine gemeinsame Liste aller zu prüfenden IP-Adressen erzeugen
                all_ips = []

                # Einige häufige IP-Adressen zuerst prüfen
                priority_ips = [
                    "192.168.1.100",
                    "192.168.1.200",
                    "192.168.1.10",
                    "192.168.1.20",
                    "192.168.0.100",
                    "192.168.0.200"
                ]

                try:
                    ip_network = IPv4Network(network)
                    local_ip = get_local_ip()

                    # Alle IP-Adressen anfügen, die häufigen zuerst
                    for ip in ip_network.hosts():
                        ip_str = str(ip)
                        if ip_str == local_ip:
                            continue  # Skip local IP

                        if ip_str in priority_ips:
                            # Die bevorzugten IP-Adressen voranstellen
                            all_ips.insert(0, ip_str)
                        else:
                            # Die übrigen IP-Adressen anhängen
                            all_ips.append(ip_str)
                except ValueError:
                    _LOGGER.error("Ungültiges Netzwerkformat: %s", network)
                    continue

                # Blockgröße für ein schnelleres Suchen optimieren
                chunk_size = 40

                # Alle IP-Adressen in einem Durchgang mit optimierten Blöcken prüfen
                for i in range(0, len(all_ips), chunk_size):
                    chunk_ips = all_ips[i:i + chunk_size]
                    _LOGGER.debug("IP-Adressen %d bis %d von %d werden geprüft",
                                 i, min(i+chunk_size, len(all_ips)), len(all_ips))

                    # Aufgaben für diesen Block erzeugen
                    chunk_tasks = [test_controme_host(session, ip) for ip in chunk_ips]

                    # Alle Aufgaben parallel ausführen
                    chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)

                    # Ergebnisse auswerten
                    discovered_systems = []
                    for ip, result in zip(chunk_ips, chunk_results):
                        if isinstance(result, Exception):
                            continue
                        if result:
                            discovered_systems.append(result)
                            _LOGGER.info("Controme-System gefunden: %s", result["url"])

                    # Wenn ein System gefunden wurde, sofort zurückkehren
                    if discovered_systems:
                        end_time = asyncio.get_event_loop().time()
                        scan_duration = end_time - start_time
                        _LOGGER.info(
                            "Netzwerksuche in %.2f Sekunden abgeschlossen. "
                            "%d Controme-Systeme gefunden",
                                   scan_duration, len(discovered_systems))
                        return discovered_systems

            except Exception as e:
                _LOGGER.error("Fehler bei der Netzwerksuche in %s: %s", network, str(e))
                continue

    # Bis hierher wurden keine Systeme gefunden
    end_time = asyncio.get_event_loop().time()
    scan_duration = end_time - start_time
    _LOGGER.info("Netzwerksuche in %.2f Sekunden abgeschlossen. Keine Controme-Systeme gefunden", scan_duration)
    return []