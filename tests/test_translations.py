"""Tests der Übersetzungen der Controme-Integration.

Die Tests prüfen, dass die deutsche und die englische Fassung zusammenpassen
und dass die Dateien den Regeln von Home Assistant entsprechen.
"""

import json
import re
from pathlib import Path

import pytest

ORDNER = Path(__file__).resolve().parents[1] / "custom_components" / "controme_connect"
TRANSLATIONEN = ORDNER / "translations"

# Der Schlüssel einer Zustandsübersetzung muss aus Kleinbuchstaben bestehen
ZUSTANDS_SCHLUESSEL = re.compile(r"^[a-z0-9-_]+$")


def lade(datei: str) -> dict:
    """Lädt eine Übersetzungsdatei."""
    return json.loads((TRANSLATIONEN / datei).read_text(encoding="utf-8"))


def alle_pfade(obj: dict, praefix: str = "") -> set:
    """Gibt alle Pfade eines verschachtelten Wörterbuchs zurück."""
    pfade = set()
    for schluessel, wert in obj.items():
        if isinstance(wert, dict):
            pfade |= alle_pfade(wert, f"{praefix}{schluessel}.")
        else:
            pfade.add(f"{praefix}{schluessel}")
    return pfade


@pytest.fixture(scope="module")
def deutsch() -> dict:
    """Die deutsche Übersetzung."""
    return lade("de.json")


@pytest.fixture(scope="module")
def englisch() -> dict:
    """Die englische Übersetzung."""
    return lade("en.json")


class TestGleicheSchluessel:
    """Beide Sprachfassungen müssen dieselben Schlüssel haben."""

    def test_gleiche_schluessel(self, deutsch, englisch):
        """Kein Schlüssel fehlt in einer der beiden Fassungen."""
        fehlend_de = alle_pfade(englisch) - alle_pfade(deutsch)
        fehlend_en = alle_pfade(deutsch) - alle_pfade(englisch)
        assert not fehlend_de, f"fehlt in de.json: {sorted(fehlend_de)}"
        assert not fehlend_en, f"fehlt in en.json: {sorted(fehlend_en)}"


class TestSchluesselFormat:
    """Home Assistant verlangt bestimmte Formate für die Schlüssel."""

    @pytest.mark.parametrize("datei", ["de.json", "en.json"])
    def test_zustandsschluessel_klein(self, datei):
        """Zustandsschlüssel müssen aus Kleinbuchstaben bestehen."""
        daten = lade(datei)
        zustaende = []

        def sammle(obj):
            if isinstance(obj, dict):
                for schluessel, wert in obj.items():
                    if schluessel == "state" and isinstance(wert, dict):
                        zustaende.extend(wert)
                    else:
                        sammle(wert)

        sammle(daten)
        ungueltig = [z for z in zustaende if not ZUSTANDS_SCHLUESSEL.match(z)]
        assert not ungueltig, f"ungültige Zustandsschlüssel: {ungueltig}"

    @pytest.mark.parametrize("datei", ["de.json", "en.json"])
    def test_keine_leeren_texte(self, datei):
        """Ein leerer Text würde in der Oberfläche als Lücke erscheinen."""
        daten = lade(datei)
        leere = []

        def sammle(obj, pfad=""):
            if isinstance(obj, dict):
                for schluessel, wert in obj.items():
                    sammle(wert, f"{pfad}{schluessel}.")
            elif isinstance(obj, str) and not obj.strip():
                leere.append(pfad)

        sammle(daten)
        assert not leere, f"leere Texte: {leere}"


class TestPlatzhalter:
    """Die Platzhalter in den Namen müssen zum Code passen."""

    @pytest.mark.parametrize("datei", ["de.json", "en.json"])
    def test_namen_ohne_platzhalter_fuer_feste_namen(self, datei):
        """Nur die beiden dynamischen Namen enthalten Platzhalter."""
        daten = lade(datei)
        entitaeten = daten.get("entity", {})
        mit_platzhalter = set()
        for domain, eintraege in entitaeten.items():
            for schluessel, eintrag in eintraege.items():
                name = eintrag.get("name", "")
                if "{" in name:
                    mit_platzhalter.add(f"{domain}.{schluessel}")
        assert mit_platzhalter == {
            "sensor.offset",
            "sensor.return_labeled",
        }, f"unerwartete Platzhalter: {mit_platzhalter}"

    def test_platzhalter_im_code(self):
        """Der Code liefert genau die Platzhalter, die die Übersetzung erwartet."""
        sensor_code = (ORDNER / "sensor.py").read_text(encoding="utf-8")
        assert '"offset"' in sensor_code
        assert '"return_labeled"' in sensor_code
        assert '_attr_translation_placeholders = {"plugin": plugin}' in sensor_code
        assert '_attr_translation_placeholders = {"label": self._return_label}' in sensor_code


class TestVollstaendigkeit:
    """Alle Entity-Arten der Integration sind übersetzt."""

    @pytest.mark.parametrize("datei", ["de.json", "en.json"])
    def test_alle_schluessel_vorhanden(self, datei):
        """Jeder im Code verwendete Übersetzungsschlüssel ist vorhanden."""
        daten = lade(datei)
        entitaeten = daten.get("entity", {})
        for domain, dateiname in (
            ("sensor", "sensor.py"),
            ("binary_sensor", "binary_sensor.py"),
        ):
            code = (ORDNER / dateiname).read_text(encoding="utf-8")
            verwendet = set(
                re.findall(r'_attr_translation_key = "([a-z_]+)"', code)
            )
            vorhanden = set(entitaeten.get(domain, {}))
            fehlend = verwendet - vorhanden
            assert not fehlend, f"{datei}: fehlt in {domain}: {sorted(fehlend)}"

    @pytest.mark.parametrize("datei", ["de.json", "en.json"])
    def test_konfigurationsschritte_vorhanden(self, datei):
        """Alle Schritte des Einrichtungsdialogs sind übersetzt."""
        daten = lade(datei)
        schritte = set(daten.get("config", {}).get("step", {}))
        erwartet = {
            "user",
            "auto_discovery",
            "credentials",
            "manual_entry",
            "select_system",
            "select_house",
            "reconfigure",
        }
        assert erwartet <= schritte, f"{datei}: fehlt: {sorted(erwartet - schritte)}"
