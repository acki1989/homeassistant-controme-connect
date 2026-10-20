# Controme Connect

Home-Assistant-Integration für Controme-Heizungsanlagen mit Smart-Heat-OS
(Mini-Server).

Die vollständige Anleitung mit Installationsschritten, allen Entities,
Dashboard-Beispielen und Problembehebung steht in der
[README des Repositories](https://github.com/<dein-nutzer>/homeassistant-controme-connect).

## Einrichtung

*Einstellungen → Geräte & Dienste → Integration hinzufügen → Controme Connect*

Die Einrichtung prüft die Zugangsdaten an der Weboberfläche der Anlage. Die
Daten-Endpunkte der API antworten auch mit einem falschen Passwort und wären
als Prüfung wirkungslos – deshalb ist der Login die einzige verlässliche
Kontrolle. Es wird erst fortgesetzt, wenn er geklappt hat.

## Technische Übersicht

| Datei | Aufgabe |
|---|---|
| `__init__.py` | Einrichtung, Hub-Gerät, Registrierung der Plattformen |
| `const.py` | Domain, Konstanten, Icon-Zuordnung, Zeitlimits |
| `coordinator.py` | Abruf der API-Daten, Hintergrundprüfung auf Updates |
| `sensor.py` | Raumsensoren, Abweichung, Übertragung, Offsets, Firmware |
| `binary_sensor.py` | Übertragungsprobleme, Firmware-Update |
| `climate.py` | Heizungs-Entities mit Raum-Icon und Attributen |
| `config_flow.py` | Einrichtung, Haus-Auswahl, Neu konfigurieren |
| `firmware.py` | Login, Versionsabfrage, Systemcheck, Haus-Erkennung |
| `helpers.py` | Raumnamen, Feuchte, Icons, Netzwerksuche |

## Verwendete Endpunkte der Controme-API

| Endpunkt | Verwendung |
|---|---|
| `/get/json/v1/<haus>/temps/` | Räume, Temperaturen, Sensoren, Offsets |
| `/get/json/v1/<haus>/rooms/` | Raumnamen und Icons |
| `/get/json/v1/<haus>/deviation/` | Abweichung zwischen Ist und Soll |
| `/get/json/v1/<haus>/info/` | Firmware-Version, Branch, Hardware |
| `/m_setup/<haus>/hardware/setup_rpi/?verdate=2` | Gibt es ein Update? (200 = ja) |
| `/m_setup/<haus>/hardware/setup_rpi/?vertarget=stable_v2&ms=2` | Aktuelle stabile Version |
| `/m_setup/<haus>/hardware/setup_rpi/?vertarget=lab_v2&ms=2` | Aktuelle Beta-Version (nur Information) |
| `/m_setup/<haus>/hardware/?overview=1` | Systemcheck je Raum |
| `/accounts/m_login/` | Anmeldung an der Weboberfläche |

Die Daten-Endpunkte sind nicht authentifiziert. Die Zugangsdaten werden
ausschließlich für den Login an der Weboberfläche benötigt.

## Grenzen

- Für Räume ohne Sensor liefert die API Platzhaltertexte; die betroffenen
  Entities stehen dann auf `unknown`.
- Die Abweichung liefert die API nur für Räume mit Vorlauftemperaturkorrektur.
- Ein Firmware-Update muss über die Weboberfläche ausgelöst werden; die
  Integration meldet es nur.
