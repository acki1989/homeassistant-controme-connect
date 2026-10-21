# Controme Connect

<img src="custom_components/controme_connect/brand/icon.png" alt="Controme Connect" width="96" align="right">

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.11%2B-blue.svg)](https://www.home-assistant.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Home-Assistant-Integration für **Controme-Heizungsanlagen mit Smart-Heat-OS** (Mini-Server).
Sie liefert die Raumtemperaturen, Rücklauftemperaturen, die Wirkung der einzelnen
Offset-Module, die Übertragungsqualität der Sensoren sowie den Firmware-Stand der
Anlage – und warnt, wenn ein Sensor nicht mehr sendet.

> **Verwandt mit**
> [homeassistant-controme-integration](https://github.com/flame4ever/homeassistant-controme-integration)
> von *flame4ever* – vielen Dank für die Grundlage. Diese Fassung ist eine
> eigenständige, erweiterte und geprüfte Variante mit eigener Domain
> (`controme_connect`) und eigenen Entity-IDs (`sensor.controme_connect_*`).

---

## Inhalt

- [Funktionen](#funktionen)
- [Installation](#installation)
- [Einrichtung](#einrichtung)
- [Konfiguration](#konfiguration)
- [Entities](#entities)
- [Besonderheiten](#besonderheiten)
- [Dashboard-Beispiele](#dashboard-beispiele)
- [Häufige Fragen](#häufige-fragen)
- [Problembehebung](#problembehebung)
- [Grenzen](#grenzen)
- [Mitwirken](#mitwirken)
- [Danksagung](#danksagung)

---

## Voraussetzungen

| | |
|---|---|
| **Home Assistant** | 2024.11 oder neuer – der Ablauf *Neu konfigurieren* wurde mit dieser Version eingeführt |
| **Anlage** | Controme-Heizungsanlage mit Smart-Heat-OS (Mini-Server) |
| **Netzwerk** | Der Mini-Server muss erreichbar sein und die Anmeldung an seiner Weboberfläche muss klappen |
| **Python-Abhängigkeiten** | keine – die Integration nutzt nur die Bibliotheken von Home Assistant |

## Funktionen

| Bereich | Was geliefert wird |
|---|---|
| **Raum** | Temperatur, Zieltemperatur, Betriebsart, Rücklauftemperatur, Luftfeuchtigkeit, Temperaturanpassung (Summe) |
| **Raum (Diagnose)** | Letzte Übertragung, Übertragung gestört, Abweichung zwischen Ist und Soll |
| **Module** | Je Offset-Modul ein eigener Sensor – nur Module, die den Raum wirklich beeinflussen |
| **Anlage** | Firmware-Stand (Version, Branch, Commit, Hardware, Betriebssystem), Hinweis auf verfügbares Update |
| **Anlage (Diagnose)** | Systemcheck der Weboberfläche: welcher Sensor steuert welchen Ausgang |

Dazu die Anzeige der **Raum-Icons** aus der Controme-Oberfläche (Sessel, Bett,
Dusche, Esstisch, …) auf den Heizungs-Entities.

## Installation

### Über HACS (empfohlen)

1. In HACS *Einstellungen → Benutzerdefiniertes Repository* hinzufügen:

   | Feld | Wert |
   |---|---|
   | Repository | `https://github.com/acki1989/homeassistant-controme-connect` |
   | Kategorie | Integration |

2. HACS die Integration **Controme Connect** suchen und *Herunterladen*.
3. Home Assistant neu starten.

### Manuell

Den Ordner `custom_components/controme_connect` aus diesem Repository in das
Konfigurationsverzeichnis von Home Assistant (`/config/custom_components/`)
kopieren und Home Assistant neu starten.

<details>
<summary>Installation per Skript aus einem geklonten Repository</summary>

```bash
git clone https://github.com/acki1989/homeassistant-controme-connect.git
cd homeassistant-controme-connect
./install.sh          # kopiert nach /config/custom_components
```

</details>

## Einrichtung

*Einstellungen → Geräte & Dienste → Integration hinzufügen → Controme Connect*

1. **Ermittlung** – entweder automatisch das Netzwerk nach Controme-Systemen
   durchsuchen oder die IP-Adresse von Hand eintragen.
2. **Zugangsdaten** – Benutzer und Passwort der Controme-Weboberfläche.
3. **Haus** – nur nötig, wenn die Anlage Daten für mehrere Häuser liefert
   (siehe [Haus-ID](#haus-id)).

> **Wichtig:** Die Einrichtung wird **erst fortgesetzt, wenn der Login an der
> Weboberfläche geklappt hat**. Die Daten-Endpunkte der Controme-API antworten
> nämlich auch mit einem falschen Passwort – sie wären als Prüfung wirkungslos.
> Der Login ist der einzige echte Test der Zugangsdaten.

## Konfiguration

Alle Angaben lassen sich später unter
*Einstellungen → Geräte & Dienste → Controme Connect → Neu konfigurieren*
ändern, ohne die Integration zu löschen.

| Option | Bedeutung |
|---|---|
| **API-Adresse** | Adresse des Mini-Servers, z. B. `192.168.178.79`. Schema und abschließender Slash sind optional. |
| **Haus-ID** | Nummer des Hauses in der Anlage, meist `2`. |
| **Benutzer** | Benutzer der Controme-Weboberfläche |
| **Passwort** | Passwort der Controme-Weboberfläche |

### Haus-ID

Die Daten-Endpunkte der API antworten für **jede** Haus-ID mit denselben
Räumen – sie taugen also nicht zur Unterscheidung. Die Weboberfläche ist
dagegen an ein Haus gebunden: Sie existiert nur unter der ID, die wirklich
eingerichtet ist. Beim Einrichten werden deshalb die IDs 1 bis 10 über die
Weboberfläche geprüft und die gültigen als Auswahl angeboten. Lässt sich die
Anlage nicht ermitteln, kann die ID von Hand eingetragen werden.

Die Haus-ID steht in den Attributen aller Entities (`house_id`) und im Namen des
Hub-Geräts (`Controme Home <Haus-ID>`). Stimmt sie nicht, meldet die
Firmware-Entity das im Log – die Raumsensoren funktionieren auch dann, nur die
Informationen zur Firmware fehlen dann.

> **Wichtig:** Die Weboberfläche lässt nur **eine** Anmeldung gleichzeitig zu.
> Betreibt man beide Integrationen parallel, kann sich die zweite Anmeldung
> gegenseitig aufheben und die Firmware-Informationen fehlen. Für den
> Regelbetrieb eine der beiden Integrationen verwenden.

## Entities

Die IDs enthalten den Raumnamen der Anlage, z. B. `Galerie` → `galerie`.

Die Namen der Entities sind übersetzt: Home Assistant zeigt sie in der Sprache
der Oberfläche an, deutsch in `translations/de.json`, englisch in
`translations/en.json`. Die Namen der Raum-Sensoren bleiben dabei gleich –
die Werte und die IDs ändern sich nicht.

### Je Raum

| Entity-ID | Name | Inhalt |
|---|---|---|
| `sensor.controme_connect_<raum>_temperature` | Temperatur | Ist-Temperatur in °C |
| `sensor.controme_connect_<raum>_target` | Zieltemperatur | Vorgesehene Solltemperatur in °C |
| `sensor.controme_connect_<raum>_mode` | Betriebsart | `heating` / `off` (Werte der Anlage in Kleinbuchstaben, in der Oberfläche übersetzt) |
| `sensor.controme_connect_<raum>_return` | Rücklauftemperatur | Rücklauf des Heizkreises in °C |
| `sensor.controme_connect_<raum>_humidity` | Luftfeuchtigkeit | relative Feuchte in % |
| `sensor.controme_connect_<raum>_offset` | Temperaturanpassung | Summe aller Offsets in °C |
| `sensor.controme_connect_<raum>_deviation` | Abweichung | Ist minus Soll in °C (2 Nachkommastellen) |
| `sensor.controme_connect_<raum>_last_transmission` | Letzte Übertragung | Zeitpunkt der jüngsten Übertragung (Diagnostic) |
| `binary_sensor.controme_connect_<raum>_transmission_problem` | Übertragung gestört | `on`, wenn ein Sensor zu lange schweigt (Diagnostic) |
| `climate.controme_connect_<raum>` | Heizung | Zieltemperatur, Ist-Temperatur, Icon, Attribute |

### Je aktivem Offset-Modul

| Entity-ID | Name |
|---|---|
| `sensor.controme_connect_<raum>_offset_<modul>` | Temperaturanpassung `<Modul>` |

Der Suffix ist der Modulname in Kleinschreibung, z. B. `wetter`,
`heizflaechenoptimierung`, `kalender`, `zeitschalter`.

### Anlage

| Entity-ID | Name | Inhalt |
|---|---|---|
| `sensor.controme_connect_firmware` | Firmware | Version, Branch, Commit, Hardware, Betriebssystem, verfügbare Version (Diagnostic) |
| `binary_sensor.controme_connect_firmware_update` | Firmware-Update verfügbar | `on`, wenn die Anlage eine neuere Version anbietet (Diagnostic) |

### Attribute

| Entity | Attribute |
|---|---|
| alle | `room_id`, `floor_id`, `house_id` |
| `…_offset_<modul>` | `plugin`, `house_offset` |
| `…_humidity` | `source` (`room` oder der Sensorname), zusätzlich `Helligkeit` und `Bewegung` der Multi-Sensoren |
| `…_last_transmission` | `oldest_sensor`, `oldest_transmission`, `timeout_minutes`, `timeout_minutes_multi`, `sensors` mit Alter je Sensor |
| `…_transmission_problem` | `oldest_sensor`, `stale_sensors`, `timeout_minutes`, `timeout_minutes_multi` |
| `…_firmware` | `sw_date`, `branch`, `commit`, `repo`, `os`, `hw`, `fbi`, `app_compatibility`, `services_paket`, `installed_branch`, `installed_build`, `miniserver`, `uptime_since`, `system_time`, `latest_version`, `lab_version`, `update_available`, `update_status`, `houses`, `system_check` |
| `climate.…` | `is_temporary_mode`, `remaining_time`, `mode_end_datetime`, `perm_target_temperature`, `controme_icon` |

## Besonderheiten

### Nur wirksame Module sind sichtbar

Eine Heizungsanlage bringt rund neun Offset-Module mit – die meisten stehen
permanent auf 0. Für jedes Modul eine Entity anzulegen würde die Liste
zuschwallen. Deshalb bekommt ein Modul **nur dann** eine Entity, wenn es den
Raum tatsächlich beeinflusst. Wird ein Modul später aktiv (etwa die
Wetterkorrektur im Winter), lädt sich die Integration selbst neu und die Entity
erscheint.

Die Namen der Module kommen unverändert aus der Anlage (z. B. „Wetter" oder
„Heizflächenoptimierung") und werden nicht übersetzt. Sie stehen auch im
Attribut `plugin`.

### Unterschiedliche Zeitlimits für die Übertragung

Die Sensoren senden unterschiedlich häufig:

| Sensortyp | Erkennung | Zeitlimit |
|---|---|---|
| Rücklauf- und Raumtemperatursensoren | Zahlenwert | 30 Minuten |
| Raumthermostate mit Solarzelle und Knopfzelle | Wert als Dictionary | 6 Stunden |

Ein solarbetriebenes Thermostat schläft zwischen den Übertragungen, ein
Timeout von 30 Minuten wäre dort ein Fehlalarm. Erkennbar sind die beiden
Typen an der Datenform der API: die Thermostate liefern mehrere Werte
(Helligkeit, Feuchte, Bewegung, Temperatur) als Dictionary, die übrigen Sensoren
einen einzelnen Zahlenwert.

### Rücklauftemperaturen

Die Anlage bezeichnet die Rücklauf-Sensoren mit der Abkürzung **„RL“** (z. B.
`Galerie RL`). Die Erkennung berücksichtigt `RL`, `Rücklauf` und `Ruecklauf`.
Führt ein Raum mehrere Rücklauf-Sensoren, werden sie eindeutig benannt
(z. B. *Wohnzimmer Ofen* und *Wohnzimmer Mitte*).

### Firmware und Updates

Die Controme-API nennt keine Update-Informationen – nur die Weboberfläche kennt
sie. Die Integration meldet sich dort an (mit den eingegebenen Daten) und liest
dort den Update-Stand ab:

- `?verdate=2` → **HTTP 200 bedeutet: es gibt ein Update**, HTTP 404 bedeutet:
  die installierte Version ist die neueste.
- `?vertarget=stable_v2` → die aktuelle stabile Version.
- `?vertarget=lab_v2` → die Beta-Version, nur zur Information.

Die Lab-Version wird **nicht** für die Update-Entscheidung verwendet – sonst
würde jede Beta ein falsches Update melden. Die Prüfung läuft im Hintergrund
alle sechs Stunden und kann die Raumsensoren nie blockieren. Wird die
Weboberfläche nicht erreicht, meldet die Entity `unknown` statt einer falschen
Aussage.

### Systemcheck

Die Weboberfläche liefert je Raum, welcher Sensor welchen Ausgang steuert. Das
ist als Attribut `system_check` an der Firmware-Entity verfügbar.

## Dashboard-Beispiele

### Alle Räume mit Temperatur und Rücklauf

```yaml
type: entities
title: Heizung
entities:
  - entity: climate.controme_connect_galerie
  - type: sensor
    entity: sensor.controme_connect_galerie_return
  - type: sensor
    entity: sensor.controme_connect_galerie_deviation
```

### Nur die Räume mit einem Problem

```yaml
type: entities
title: Achtung Heizung
entities:
  - type: sensor
    entity: sensor.controme_connect_firmware_update
    name: Firmware-Update verfügbar
  - type: sensor
    entity: binary_sensor.controme_connect_galerie_transmission_problem
    name: Galerie
  - type: sensor
    entity: binary_sensor.controme_connect_toni_transmission_problem
    name: Toni
```

### Karte mit der Raumtemperatur

```yaml
type: tile
entity: sensor.controme_connect_galerie_temperature
name: Galerie
vertical: true
features_position: bottom
color: blue
```

## Häufige Fragen

**Warum stehen alle Luftfeuchten auf `unknown`?**
Weil in den Räumen kein Feuchtesensor verbaut ist. Sobald einer nachgerüstet
wird, erscheint der Wert automatisch – die Entity existiert bereits.

**Warum fehlen die Offsets der Module?**
Weil sie den Raum derzeit nicht beeinflussen. Sobald ein Modul aktiv wird,
erscheint die Entity.

**Die Anlage hat mehrere Häuser.**
Beim Einrichten werden die unterschiedlichen Haus-IDs zur Auswahl angeboten.
Lässt sich die Anlage später umstellen, geht das über *Neu konfigurieren*.

**Kann ich die Heizung von Home Assistant aus steuern?**
Ja, die Climate-Entities erlauben das Setzen der Zieltemperatur.

**Was passiert bei einem Ausfall der Anlage?**
Die Entities wechseln auf `unavailable`, das Log nennt den Grund in einer Zeile,
und beim nächsten erfolgreichen Abruf sind die Werte wieder da. Der
Firmware-Check läuft davon unbeeinflusst im Hintergrund.

## Problembehebung

| Meldung | Ursache und Abhilfe |
|---|---|
| *Controme Anlage nicht erreichbar* | Die IP-Adresse ist falsch oder die Anlage antwortet nicht. Netzwerkverbindung und Adresse prüfen. |
| *Benutzername oder Passwort ist ungültig* | Die Weboberfläche lehnt die Daten ab. In der Weboberfläche anmelden und dort ein neues Passwort setzen. |
| *Keine Räume sichtbar* | Die Haus-ID stimmt nicht. Über *Neu konfigurieren* eine andere ID wählen. |
| *Firmware-Update meldet `unknown`* | Die Weboberfläche ist nicht erreichbar oder der Login schlägt fehl. `update_status` an der Firmware-Entity nennt den Grund. |
| *Übertragung gestört bleibt an* | Ein Sensor sendet zu lange nicht. `stale_sensors` an der Entity nennt den Sensor. |

## Grenzen

- Die Daten-Endpunkte der Controme-API sind nicht authentifiziert. Die
  Zugangsdaten werden nur für den Login an der Weboberfläche benötigt.
- Für Räume ohne Sensor liefert die API Platzhaltertexte („kein Sensor
  vorhanden“). Die betroffenen Entities stehen dann auf `unknown`.
- Die Abweichung (Ist zu Soll) liefert die API nur für Räume mit
  Vorlauftemperaturkorrektur.
- Historie und Statistik liegen im lokalen Recorder von Home Assistant und
  werden beim Wechsel der Integration nicht übernommen.
- Ein Update der Firmware selbst muss über die Weboberfläche der Anlage
  ausgelöst werden; die Integration meldet es nur.

## Veröffentlichung

Das Repository liegt auf GitHub unter
[acki1989/homeassistant-controme-connect](https://github.com/acki1989/homeassistant-controme-connect)
und ist über HACS installierbar.

### Installation über HACS

1. In HACS *Einstellungen → Benutzerdefiniertes Repository* hinzufügen:

   | Feld | Wert |
   |---|---|
   | Repository | `https://github.com/acki1989/homeassistant-controme-connect` |
   | Kategorie | Integration |

2. **Controme Connect** suchen und herunterladen.
3. Home Assistant neu starten.

### Installation ohne HACS

```bash
git clone https://github.com/acki1989/homeassistant-controme-connect.git
cd homeassistant-controme-connect
./install.sh          # kopiert nach /config/custom_components
```

Danach Home Assistant neu starten.

### Eigene Weiterentwicklung

```bash
cd /config/homeassistant-controme-connect
git pull              # Änderungen aus dem Repository übernehmen
```

Bei jedem Push läuft die GitHub-Actions-Prüfung *Validate* (hassfest) und
meldet Fehler im Manifest, in den Übersetzungen oder im Code.

## Mitwirken

Fehler und Verbesserungen sind willkommen – bitte als
[Issue](https://github.com/acki1989/homeassistant-controme-connect/issues)
melden. Codeänderungen bitte als Pull Request einreichen.

```
custom_components/controme_connect/
├── __init__.py         Einrichtung, Hub-Gerät, Plattform-Registrierung
├── const.py            Konstanten, Icon-Zuordnung, Zeitlimits
├── coordinator.py      API-Abruf, Hintergrundprüfung auf Updates
├── sensor.py           Raumsensoren, Abweichung, Übertragung, Offsets, Firmware
├── binary_sensor.py    Übertragungsprobleme, Firmware-Update
├── climate.py          Heizungs-Entities mit Raum-Icon
├── config_flow.py      Einrichtung, Haus-Auswahl, Neu konfigurieren
├── firmware.py         Login, Versionsabfrage, Systemcheck, Haus-Erkennung
└── helpers.py          Namen, Feuchte, Icons, Netzwerksuche
```

Die Integration braucht keine zusätzlichen Python-Abhängigkeiten und läuft
vollständig im lokalen Netz.

### Tests

Die reinen Hilfsfunktionen sind durch Unit-Tests abgedeckt:

```bash
pip install pytest aiohttp
python -m pytest tests/
```

## Danksagung

- **flame4ever** für die ursprüngliche
  [homeassistant-controme-integration](https://github.com/flame4ever/homeassistant-controme-integration)
- **Controme** für die dokumentierte
  [Smart-Heat-OS-API](https://support.controme.com/api/)

## Marken und Logos

**Controme**, **Smart-Heat-OS** und das Controme-Logo sind Marken der
Controme GmbH. Diese Integration steht in keiner Verbindung zu Controme und
wird von Controme weder unterstützt noch empfohlen. Das Logo wird im
README nicht verwendet; benannt wird ausschließlich das Produkt, um die
Kompatibilität zu beschreiben.

**Home Assistant** und das Home-Assistant-Logo sind Marken der Open Home
Foundation. Sie erscheinen hier nur, um die Kompatibilität anzuzeigen –
eine offizielle Partnerschaft oder Empfehlung ist damit nicht verbunden.

Das Icon und das Logo dieser Integration (`brand/icon.png`,
`brand/logo.png`) sind eigene Grafiken, erzeugt mit
`tools/create_brand_images.py`.

## Lizenz

MIT – siehe [LICENSE](LICENSE). Die ursprüngliche Integration steht unter der
MIT-Lizenz von *flame4ever*, diese Fassung ist eine davon abgeleitete
Weiterentwicklung.
