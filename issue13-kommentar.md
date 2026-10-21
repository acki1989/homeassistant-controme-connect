# Kommentar für Upstream-Issue #13

**Issue:** https://github.com/flame4ever/homeassistant-controme-integration/issues/13
(Titel: „No Sensor Return Temperature“, offen seit 02.10.2025)

Anleitung: Issue im Browser öffnen → „New comment" → Text aus dem Abschnitt
„Zu kopierender Text" unten einfügen → „Comment" klicken.

---

## Zu kopierender Text

The API does not use the word "Rücklauf" in the sensor description.
On my system (Smart-Heat-OS 5.62) get/json/v1/2/temps/ returns:

```
{ "name": "28_08_7b_8e_09_00_00_e0", "wert": 23.81, "beschreibung": "Galerie RL" }
```

So the check in sensor.py never matches:

```python
for sensor in room.get("sensoren", []):
    if "Rücklauf" in sensor.get("beschreibung", ""):
```

Matching "RL" as a standalone token works for all 12 rooms of my installation.
The same endpoint rltemps/[room-id] also reports the description as "… RL".

A second issue: the entity_id is always built as
"sensor.controme_<room>_return", so a room with more than one RL sensor
(e.g. "Wohnzimmer Ofen RL" and "Wohnzimmer Mitte RL" in one room) would
produce duplicate entity_ids and abort the whole sensor platform setup.
The room/sensor name should be part of the entity_id.

---

## Kontext / Hintergrund (nicht mitschicken)

- Betroffene Datei: `custom_components/controme/sensor.py` (v1.1.2, identisch mit main)
- Lokale Umgebung: Home Assistant 2026.10.2, Controme Mini-Server 192.168.178.79,
  Smart-Heat-OS 5.62, Haus-ID 2
- API-Beispiel-Daten (Mini-Server, `/get/json/v1/2/temps/`):

  | Raum | Sensorbeschreibung | Wert |
  |---|---|---|
  | Galerie | „Galerie RL" | 23,81 °C |
  | Schlafzimmer Eltern | „Schlafzimmer Eltern RL" | 23,81 °C |
  | Bad oben | „Bad oben RL" | 24,12 °C |
  | Toni | „Toni RL" | 23,94 °C |
  | Wz Ofen | „Wohnzimmer Ofen RL" / „Wohnzimmer Mitte RL" | 26,19 °C |
  | Küche | „Küche RL" | 26,19 °C |
  | Wz Essen | „Wohnzimmer Essen RL" | 26,31 °C |
  | Leo | „Leo RL" | 26,50 °C |
  | Gäste WC | „Gäste WC RL" | 26,25 °C |
  | Flur | „Flur RL" | 26,62 °C |
  | Bad unten | „Bad unten RL" | 26,81 °C |
  | Büro | „Büro RL" | 26,69 °C |

  Nicht-Rücklauf-Sensoren, die **nicht** matchen dürfen:
  „Galerie Flur ", „Küche RT", „Bad oben ", „Wohnzimmer Ofen RT",
  „Vorlauftemperatur Fußbodenheizung ", „Vorlauftemperatur Gas"

  → deshalb „RL" nur als eigenständiges Token (`\brl\b`), nicht als Teilstring
  (sonst würde „Vorlauftemperatur" mitmatchen).
