"""Tests der reinen Hilfsfunktionen der Controme-Integration."""

from datetime import datetime

import pytest

from controme_connect.helpers import (
    extract_humidity,
    extract_multi_sensor_values,
    is_active_offset,
    is_return_sensor,
    parse_number,
    parse_transmission,
    return_label,
    room_icon,
    room_slug,
)


class TestRoomSlug:
    """Der Slug wird für die Entity-IDs der Räume verwendet."""

    @pytest.mark.parametrize(
        ("name", "erwartet"),
        [
            ("Galerie ", "galerie"),
            ("Wärmetauscher ", "warmetauscher"),
            ("Bad unten ", "bad_unten"),
            ("Gäste WC ", "gaste_wc"),
            ("Schlafzimmer Eltern ", "schlafzimmer_eltern"),
            ("", ""),
        ],
    )
    def test_slug(self, name, erwartet):
        """Der Name wird in einen reinen ASCII-Slug umgewandelt."""
        assert room_slug(name) == erwartet

    def test_kein_doppelter_unterstrich(self):
        """Der abschließende Leerzeichen des Raumnamens erzeugt keinen Doppelstrich."""
        assert "__" not in room_slug("Galerie ")
        assert room_slug("Galerie ") != "galerie_"


class TestRoomIcon:
    """Die Raum-Icons werden auf Material-Design-Icons abgebildet."""

    def test_bekanntes_icon(self):
        """Ein bekanntes Icon wird abgebildet."""
        assert room_icon("sessel") == "mdi:sofa"

    def test_unbekanntes_icon(self):
        """Ein unbekanntes Icon führt zum Ersatz-Icon."""
        from controme_connect.const import DEFAULT_ROOM_ICON

        assert room_icon("gibtesnicht") == DEFAULT_ROOM_ICON


class TestRuecklaufSensoren:
    """Die Rücklauf-Sensoren werden an ihrer Kurzbezeichnung erkannt."""

    @pytest.mark.parametrize(
        "beschreibung",
        ["Galerie RL", "RL", "Wohnzimmer Rücklauf", "Ruecklauf", "rl"],
    )
    def test_erkannt(self, beschreibung):
        """Die Kurzbezeichnung und das ganze Wort werden erkannt."""
        assert is_return_sensor(beschreibung) is True

    @pytest.mark.parametrize("beschreibung", ["Temperatur", "Sollwert", "", "Raum"])
    def test_nicht_erkannt(self, beschreibung):
        """Andere Sensoren werden nicht erkannt."""
        assert is_return_sensor(beschreibung) is False

    def test_label_enthaelt_den_raum(self):
        """Das Label trennt die Sensoren eines Raums voneinander."""
        assert return_label("Wohnzimmer Ofen RL", "Wz Ofen") == "Wohnzimmer Ofen"

    def test_label_entfernt_den_raumnamen(self):
        """Ein Label, das nur aus dem Raumnamen besteht, bleibt leer."""
        assert return_label("Wz Ofen RL", "Wz Ofen") == ""


class TestOffsets:
    """Nur Module mit einem echten Einfluss bekommen eine Entity."""

    @pytest.mark.parametrize(
        ("werte", "erwartet"),
        [
            ({"raum": 0.1, "haus": 0.0}, True),
            ({"raum": -0.1, "haus": 0.0}, True),
            ({"raum": 0.0, "haus": 0.0}, False),
            ({"raum": 0, "haus": 0}, False),
            ({"haus": 0.5}, False),
            ({}, False),
            (None, False),
            ("keine Zahl", False),
        ],
    )
    def test_aktiv(self, werte, erwartet):
        """Ein Offset von null wirkt sich nicht auf den Raum aus."""
        assert is_active_offset(werte) is erwartet


class TestParseNumber:
    """Die Werte der Anlage werden in Zahlen umgewandelt."""

    def test_null_ist_ein_wert(self):
        """Eine echte Null ist ein Messwert und darf nicht als fehlend gelten."""
        assert parse_number(0.0) == 0.0
        assert parse_number(0) == 0.0

    def test_platzhaltertext(self):
        """Platzhaltertexte der Anlage ergeben keinen Wert."""
        assert parse_number("kein Sensor vorhanden") is None
        assert parse_number("kein aktueller Wert vorhanden") is None

    def test_leerer_wert(self):
        """Fehlende Werte ergeben keinen Wert."""
        assert parse_number(None) is None
        assert parse_number("") is None

    def test_zahlen(self):
        """Zahlen und Zahlen als Text werden umgewandelt."""
        assert parse_number("20.5") == 20.5
        assert parse_number(-1.5) == -1.5
        assert parse_number(21) == 21.0


class TestParseTransmission:
    """Der Zeitpunkt der letzten Übertragung wird ausgewertet."""

    def test_deutsches_format(self):
        """Das von der Anlage gelieferte Format wird gelesen."""
        ergebnis = parse_transmission("20.10.2026 21:43")
        assert ergebnis is not None
        assert (ergebnis.year, ergebnis.month, ergebnis.day) == (2026, 10, 20)
        assert (ergebnis.hour, ergebnis.minute) == (21, 43)

    def test_iso_format(self):
        """Auch das ISO-Format wird gelesen."""
        ergebnis = parse_transmission("2026-10-20T21:26:00+02:00")
        assert ergebnis is not None
        assert ergebnis.year == 2026

    def test_ohne_zeitstempel(self):
        """Ohne Zeitstempel gibt es auch keinen Wert."""
        assert parse_transmission("") is None
        assert parse_transmission("unsinn") is None

    def test_ortszeit(self):
        """Die Anlage meldet Ortszeiten, der Wert hat deshalb eine Zeitzone."""
        ergebnis = parse_transmission("20.10.2026 21:43")
        assert isinstance(ergebnis, datetime)
        assert ergebnis.tzinfo is not None


class TestFeuchte:
    """Die Luftfeuchte kommt aus dem Raum oder aus den Multi-Sensoren."""

    def test_aus_dem_raum(self):
        """Ein verbauter Feuchtesensor liefert den Wert direkt."""
        feuchte, quelle = extract_humidity({"luftfeuchte": 55.5})
        assert feuchte == 55.5
        assert quelle == "room"

    def test_platzhaltertext(self):
        """Der Platzhaltertext der Anlage ist kein Messwert."""
        feuchte, quelle = extract_humidity({"luftfeuchte": "kein Sensor vorhanden"})
        assert feuchte is None

    def test_aus_multi_sensor(self):
        """Fehlt der Raumsensor, wird der Multi-Sensor verwendet."""
        raum = {
            "luftfeuchte": "kein Sensor vorhanden",
            "sensoren": [
                {
                    "name": "Thermostat",
                    "beschreibung": "Wohnzimmer",
                    "wert": {
                        "Temperatur": 20.5,
                        "Relative Luftfeuchte": 48.0,
                        "Helligkeit": 120,
                    },
                }
            ],
        }
        feuchte, quelle = extract_humidity(raum)
        assert feuchte == 48.0
        assert quelle == "Wohnzimmer"

    def test_ohne_sensor(self):
        """Ohne jeden Sensor gibt es keinen Feuchtewert."""
        assert extract_humidity({"luftfeuchte": "kein Sensor vorhanden"}) == (None, None)

    def test_multi_sensor_werte(self):
        """Helligkeit und Bewegung werden zusätzlich geliefert."""
        raum = {
            "sensoren": [
                {
                    "name": "Thermostat",
                    "wert": {
                        "Temperatur": 20.5,
                        "Relative Luftfeuchte": 48.0,
                        "Helligkeit": 120,
                        "Bewegung": True,
                    },
                }
            ]
        }
        werte = extract_multi_sensor_values(raum)
        assert werte == {"Helligkeit": 120, "Bewegung": True}
