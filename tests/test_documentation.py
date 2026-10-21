"""Tests der Dokumentation der Controme-Integration.

Die deutsche und die englische README müssen denselben Inhalt beschreiben.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
README_DE = REPO / "README.md"
README_EN = REPO / "README.en.md"

# Die Abschnitte der deutschen README und ihre englische Entsprechung
ABSCHNITTE = {
    "Voraussetzungen": "Prerequisites",
    "Funktionen": "Features",
    "Installation": "Installation",
    "Einrichtung": "Setup",
    "Konfiguration": "Configuration",
    "Entities": "Entities",
    "Besonderheiten": "Notes",
    "Dashboard-Beispiele": "Dashboard examples",
    "Häufige Fragen": "Frequently asked questions",
    "Problembehebung": "Troubleshooting",
    "Grenzen": "Limitations",
    "Veröffentlichung": "Publishing",
    "Mitwirken": "Contributing",
    "Danksagung": "Acknowledgements",
    "Marken und Logos": "Trademarks and logos",
    "Lizenz": "License",
}

# Platzhalter, die in einer veröffentlichten Fassung nichts zu suchen haben
PLATZHALTER = ("<dein-nutzer>", "<your-user>", "TODO", "FIXME", "XXX")


@pytest.fixture(scope="module")
def deutsch() -> str:
    """Der Inhalt der deutschen README."""
    return README_DE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def englisch() -> str:
    """Der Inhalt der englischen README."""
    return README_EN.read_text(encoding="utf-8")


class TestAbschnitte:
    """Beide Fassungen müssen dieselben Abschnitte enthalten."""

    @pytest.mark.parametrize(("abschnitt_de", "abschnitt_en"), list(ABSCHNITTE.items()))
    def test_abschnitt_vorhanden(self, deutsch, englisch, abschnitt_de, abschnitt_en):
        """Jeder deutsche Abschnitt hat eine englische Entsprechung."""
        assert f"## {abschnitt_de}" in deutsch
        assert f"## {abschnitt_en}" in englisch

    def test_keine_zusatzabschnitte(self, deutsch, englisch):
        """Die englische Fassung hat keine Abschnitte ohne Gegenstück."""
        erlaubt = set(ABSCHNITTE.values()) | {"Inhalt", "Table of contents"}
        gefunden = {
            zeile[3:].strip()
            for zeile in englisch.splitlines()
            if zeile.startswith("## ")
        }
        unbekannt = gefunden - erlaubt
        assert not unbekannt, f"unerwartete Abschnitte: {sorted(unbekannt)}"


class TestInhalt:
    """Beide Fassungen müssen denselben Stand beschreiben."""

    @pytest.mark.parametrize("datei", [README_DE, README_EN])
    def test_keine_platzhalter(self, datei):
        """In einer veröffentlichten Fassung stehen keine Platzhalter."""
        inhalt = datei.read_text(encoding="utf-8")
        gefunden = [p for p in PLATZHALTER if p in inhalt]
        assert not gefunden, f"{datei.name}: Platzhalter {gefunden}"

    @pytest.mark.parametrize("datei", [README_DE, README_EN])
    def test_repository_url(self, datei):
        """Beide Fassungen nennen das eigene Repository."""
        inhalt = datei.read_text(encoding="utf-8")
        assert "github.com/acki1989/homeassistant-controme-connect" in inhalt

    @pytest.mark.parametrize("datei", [README_DE, README_EN])
    def test_entity_prefix(self, datei):
        """Alle dokumentierten Entity-IDs nutzen die eigene Domain."""
        inhalt = datei.read_text(encoding="utf-8")
        for entity_id in re.findall(
            r"`(?:sensor|binary_sensor|climate)\.[a-z0-9_]+`", inhalt
        ):
            assert ".controme_connect_" in entity_id, f"fremde Entity-ID: {entity_id}"

    @pytest.mark.parametrize("datei", [README_DE, README_EN])
    def test_hacs_badge(self, datei):
        """Beide Fassungen haben das HACS-Badge."""
        inhalt = datei.read_text(encoding="utf-8")
        assert "img.shields.io/badge/HACS-Custom" in inhalt

    def test_haus_id_erklaert(self, deutsch, englisch):
        """Beide Fassungen erklären die Haus-ID."""
        assert "Haus-ID" in deutsch
        assert "house" in englisch.lower()

    def test_fuer_und_gegen_marken(self, deutsch, englisch):
        """Beide Fassungen enthalten den Hinweis zu den Markenrechten."""
        assert "Marken" in deutsch
        assert "trademark" in englisch.lower()
        assert "Controme GmbH" in deutsch
        assert "Controme GmbH" in englisch
