"""Tests der Firmware-Hilfsfunktionen der Controme-Integration."""

from datetime import datetime

import pytest

from controme_connect.firmware import (
    extract_short_version,
    parse_overview,
    parse_update_section,
    parse_version,
)


class TestParseVersion:
    """Die Versionsangaben der Anlage werden ausgewertet."""

    def test_iso_format(self):
        """Der Mini-Server meldet den installierten Build im ISO-Format."""
        ergebnis = parse_version("2026-07-23T12:04:07")
        assert ergebnis is not None
        assert (ergebnis.year, ergebnis.month, ergebnis.day) == (2026, 7, 23)

    def test_deutsches_format(self):
        """Die Weboberfläche verwendet das deutsche Datumsformat."""
        ergebnis = parse_version("23.07.2026 10:04:07")
        assert ergebnis is not None
        assert (ergebnis.year, ergebnis.month, ergebnis.day) == (2026, 7, 23)
        assert (ergebnis.hour, ergebnis.minute) == (10, 4)

    def test_ohne_version(self):
        """Ohne Angabe gibt es keinen Zeitpunkt."""
        assert parse_version("") is None
        assert parse_version("unbekannt") is None


class TestExtractShortVersion:
    """Die kurze Versionsangabe wird aus dem HTML der Oberfläche gelesen."""

    def test_version_gefunden(self):
        """Eine Versionsangabe im Text wird erkannt."""
        html = "<p>Version: 23.07.2026 10:04:07</p>"
        assert extract_short_version(html) == "23.07.2026 10:04:07"

    def test_ohne_version(self):
        """Ohne Versionsangabe gibt es keinen Wert."""
        assert extract_short_version("<p>keine Angabe</p>") is None


class TestParseUpdateSection:
    """Der Abschnitt zur Softwareaktualisierung wird ausgelesen."""

    def test_abschnitt(self):
        """Die Felder des Abschnitts werden übernommen."""
        html = """
        <div id="update">
            <span class="installed">23.07.2026 10:04:07</span>
            <span class="available">24.07.2026 09:00:00</span>
            <span class="branch">stable_v2</span>
        </div>
        """
        ergebnis = parse_update_section(html)
        assert isinstance(ergebnis, dict)

    def test_ohne_abschnitt(self):
        """Ohne den Abschnitt bleibt das Ergebnis leer."""
        assert parse_update_section("<html><body>nichts</body></html>") == {}


class TestParseOverview:
    """Der Systemcheck der Weboberfläche wird in eine lesbare Liste gewandelt."""

    def test_liste(self):
        """Jeder Abschnitt des Systemchecks wird übernommen."""
        daten = [
            {
                "heading": "Obergeschoss / Galerie ",
                "status": '<span style="color: green;">&#10003;</span>',
                "text": [
                    ["Raumtemperatursensor: Mehrfachsensor Galerie Flur  "],
                    ["Rücklaufsensor Galerie RL steuert"],
                    ["Ausgang 13 an Gateway Pro Gateway  auf 0"],
                ],
            }
        ]
        ergebnis = parse_overview(daten)
        assert len(ergebnis) == 1
        assert ergebnis[0]["heading"] == "Obergeschoss / Galerie "
        assert ergebnis[0]["text"] == [
            "Raumtemperatursensor: Mehrfachsensor Galerie Flur  ",
            "Rücklaufsensor Galerie RL steuert",
            "Ausgang 13 an Gateway Pro Gateway  auf 0",
        ]

    def test_leere_angabe(self):
        """Eine unerwartete Angabe ergibt eine leere Liste."""
        assert parse_overview(None) == []
        assert parse_overview({}) == []
        assert parse_overview([]) == []
