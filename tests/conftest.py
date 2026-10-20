"""Gemeinsame Vorbereitung der Tests.

Die Integration braucht Home Assistant nur für wenige Konstanten. Damit die
reinen Funktionen ohne laufende Instanz geprüft werden können, werden diese
Module minimal nachgebildet.
"""

import sys
import types
from datetime import datetime, timezone
from pathlib import Path

# Das Verzeichnis mit den Integrationen in den Suchpfad aufnehmen
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components"))

# Das Paket ohne sein __init__.py laden. Sonst würde beim Import der
# Hilfsfunktionen das ganze Home-Assistant-Framework mitgeladen.
PAKET = types.ModuleType("controme_connect")
PAKET.__path__ = [  # type: ignore[attr-defined]
    str(Path(__file__).resolve().parents[1] / "custom_components" / "controme_connect")
]
sys.modules["controme_connect"] = PAKET

HA = types.ModuleType("homeassistant")
HA.__path__ = []  # type: ignore[attr-defined]

CONST = types.ModuleType("homeassistant.const")


class Platform:
    """Nachbildung der Home-Assistant-Plattformnamen."""

    SENSOR = "sensor"
    CLIMATE = "climate"
    BINARY_SENSOR = "binary_sensor"


CONST.Platform = Platform  # type: ignore[attr-defined]

UTIL = types.ModuleType("homeassistant.util")
UTIL.__path__ = []  # type: ignore[attr-defined]

DT = types.ModuleType("homeassistant.util.dt")
DT.now = lambda: datetime.now().astimezone()  # type: ignore[attr-defined]
DT.utcnow = lambda: datetime.now(timezone.utc)  # type: ignore[attr-defined]

UTIL.dt = DT  # type: ignore[attr-defined]
HA.const = CONST  # type: ignore[attr-defined]
HA.util = UTIL  # type: ignore[attr-defined]

sys.modules.setdefault("homeassistant", HA)
sys.modules.setdefault("homeassistant.const", CONST)
sys.modules.setdefault("homeassistant.util", UTIL)
sys.modules.setdefault("homeassistant.util.dt", DT)
