# Controme Connect

<img src="custom_components/controme_connect/brand/icon.png" alt="Controme Connect" width="96" align="right">

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.11%2B-blue.svg)](https://www.home-assistant.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Home Assistant integration for **Controme heating systems running Smart-Heat-OS**
(mini server). It provides room temperatures, return flow temperatures, the
effect of each offset module, the transmission quality of the sensors and the
firmware state of the system – and warns when a sensor stops reporting.

> **Related to**
> [homeassistant-controme-integration](https://github.com/flame4ever/homeassistant-controme-integration)
> by *flame4ever* – many thanks for the foundation. This version is a
> standalone, extended and thoroughly tested variant with its own domain
> (`controme_connect`) and its own entity IDs (`sensor.controme_connect_*`).

---

## Table of contents

- [Features](#features)
- [Installation](#installation)
- [Setup](#setup)
- [Configuration](#configuration)
- [Entities](#entities)
- [Notes](#notes)
- [Dashboard examples](#dashboard-examples)
- [Frequently asked questions](#frequently-asked-questions)
- [Troubleshooting](#troubleshooting)
- [Limitations](#limitations)
- [Publishing](#publishing)
- [Contributing](#contributing)
- [Acknowledgements](#acknowledgements)
- [Trademarks and logos](#trademarks-and-logos)
- [License](#license)

---

## Prerequisites

| | |
|---|---|
| **Home Assistant** | 2024.11 or newer – the *Reconfigure* flow was introduced with that release |
| **System** | Controme heating system running Smart-Heat-OS (mini server) |
| **Network** | The mini server must be reachable and the login to its web interface must succeed |
| **Python dependencies** | none – the integration only uses the libraries shipped with Home Assistant |

## Features

| Area | What is provided |
|---|---|
| **Room** | Temperature, target temperature, operating mode, return flow temperature, humidity, total offset |
| **Room (diagnostics)** | Last transmission, transmission problem, deviation between current and target |
| **Modules** | One sensor per offset module – only the modules that really affect the room |
| **System** | Firmware state (version, branch, commit, hardware, operating system), update hint |
| **System (diagnostics)** | System check of the web interface: which sensor drives which output |

The room icons from the Controme interface (armchair, bed, shower, dining
table, …) are applied to the climate entities.

## Installation

### HACS (recommended)

1. In HACS add *Settings → Custom repositories*:

   | Field | Value |
   |---|---|
   | Repository | `https://github.com/acki1989/homeassistant-controme-connect` |
   | Category | Integration |

2. Search for **Controme Connect** in HACS and download it.
3. Restart Home Assistant.

### Manual

Copy the folder `custom_components/controme_connect` from this repository into
the Home Assistant configuration directory (`/config/custom_components/`) and
restart Home Assistant.

<details>
<summary>Installation with a script from a cloned repository</summary>

```bash
git clone https://github.com/acki1989/homeassistant-controme-connect.git
cd homeassistant-controme-connect
./install.sh          # copies to /config/custom_components
```

</details>

## Setup

*Settings → Devices & Services → Add integration → Controme Connect*

1. **Discovery** – scan the network for Controme systems automatically, or
   enter the IP address manually.
2. **Credentials** – user and password of the Controme web interface.
3. **House** – only needed if the system delivers data for several houses.

> **Important:** The setup only continues once the login to the web interface
> succeeds. The data endpoints of the Controme API answer every request, even
> with a wrong password, so they would be useless as a check. The login is the
> only reliable test of the access data.

## Configuration

All settings can be changed later under
*Settings → Devices & Services → Controme Connect → Reconfigure*.

| Option | Meaning |
|---|---|
| **API address** | Address of the mini server, e.g. `192.168.178.79`. Scheme and trailing slash are optional. |
| **House ID** | Number of the house within the system, usually `2`. |
| **User** | User of the Controme web interface |
| **Password** | Password of the Controme web interface |

### House ID

The data endpoints of the API answer with the same rooms for **every** house
ID – they are therefore useless to tell the houses apart. The web interface on
the other hand is bound to a house: it only exists under the ID that is
actually configured. During the setup the IDs 1 to 10 are therefore checked via
the web interface and the valid ones are offered as a choice. If the system
cannot be determined, the ID can be entered by hand.

The house ID is part of the attributes of all entities (`house_id`) and in the
name of the hub device (`Controme Home <house ID>`). If it is wrong, the
firmware entity reports it in the log – the room sensors work nevertheless,
only the firmware information is missing.

> **Important:** The web interface only allows **one** login at a time. If you
> operate both integrations in parallel, the second login can cancel the first
> one and the firmware information is missing. Use only one of the two
> integrations in regular operation.

## Entities

The IDs contain the room name of the system, e.g. `Galerie` → `galerie`.

The entity names are translated: Home Assistant shows them in the language of
the user interface, German in `translations/de.json`, English in
`translations/en.json`. The names of the room sensors stay the same – neither
the values nor the IDs change.

### Per room

| Entity ID | Name |
|---|---|
| `sensor.controme_connect_<room>_temperature` | Temperature |
| `sensor.controme_connect_<room>_target` | Target temperature |
| `sensor.controme_connect_<room>_mode` | Operation mode (`heating` / `off`) |
| `sensor.controme_connect_<room>_return` | Return flow temperature |
| `sensor.controme_connect_<room>_humidity` | Humidity |
| `sensor.controme_connect_<room>_offset` | Temperature adjustment (sum) |
| `sensor.controme_connect_<room>_deviation` | Deviation (current minus target) |
| `sensor.controme_connect_<room>_last_transmission` | Last transmission |
| `binary_sensor.controme_connect_<room>_transmission_problem` | Transmission problem |
| `climate.controme_connect_<room>` | Heating |

### Per active offset module

| Entity ID | Name |
|---|---|
| `sensor.controme_connect_<room>_offset_<module>` | Temperature adjustment `<module>` |

The suffix is the module name in lower case, e.g. `wetter`,
`heizflaechenoptimierung`, `kalender`, `zeitschalter`.

### System

| Entity ID | Name |
|---|---|
| `sensor.controme_connect_firmware` | Firmware |
| `binary_sensor.controme_connect_firmware_update` | Firmware update available |

### Attributes

| Entity | Attribute |
|---|---|
| all | `room_id`, `floor_id`, `house_id` |
| `…_offset_<module>` | `plugin`, `house_offset` |
| `…_humidity` | `source` (`room` or the name of the sensor), plus `Helligkeit` and `Bewegung` of the multi sensors |
| `…_last_transmission` | `oldest_sensor`, `oldest_transmission`, `timeout_minutes`, `timeout_minutes_multi`, `sensors` with the age of every sensor |
| `…_transmission_problem` | `oldest_sensor`, `stale_sensors`, `timeout_minutes`, `timeout_minutes_multi` |
| `…_firmware` | `sw_date`, `branch`, `commit`, `repo`, `os`, `hw`, `fbi`, `app_compatibility`, `services_paket`, `installed_branch`, `installed_build`, `miniserver`, `uptime_since`, `system_time`, `latest_version`, `lab_version`, `update_available`, `update_status`, `houses`, `system_check` |
| `climate.…` | `is_temporary_mode`, `remaining_time`, `mode_end_datetime`, `perm_target_temperature`, `controme_icon` |

## Notes

### Only effective modules are visible

A heating system provides about nine offset modules – most of them are
permanently at zero. An entity for every module would flood the list. A module
therefore only gets an entity when it really affects the room. If it becomes
active later (for example the weather correction in winter), the integration
reloads itself and the entity appears.

The names of the modules come unchanged from the system (e.g. "Wetter" or
"Heizflächenoptimierung") and are not translated. They are also available in
the `plugin` attribute.

### Different timeouts for the transmission

The sensors report at different intervals:

| Sensor type | Detection | Timeout |
|---|---|---|
| Return flow and room temperature sensors | numeric value | 30 minutes |
| Room thermostats with solar cell and button cell | value as a dictionary | 6 hours |

A solar powered thermostat sleeps between the transmissions, a timeout of 30
minutes would be a false alarm there. Both types are recognisable by the shape
of the data of the API: the thermostats deliver several values (brightness,
humidity, motion, temperature) as a dictionary, all other sensors a single
number.

### Return flow temperatures

The system abbreviates the return flow sensors as **"RL"** (e.g. `Galerie RL`).
The detection covers `RL`, `Rücklauf` and `Ruecklauf`. If a room has several
return flow sensors, they are named unambiguously (e.g. *Wohnzimmer Ofen* and
*Wohnzimmer Mitte*).

### Firmware and updates

The Controme API does not name any update information – only the web interface
knows them. The integration logs in there (with the data you entered) and reads
the update state from that page:

- `?verdate=2` → **HTTP 200 means: there is an update**, HTTP 404 means: the
  installed version is the latest one.
- `?vertarget=stable_v2` → the current stable version.
- `?vertarget=lab_v2` → the beta version, for information only.

The lab version is **not** used for the update decision – otherwise every beta
would report a false update. The check runs in the background every six hours
and can never block the room sensors. If the web interface cannot be reached,
the entity reports `unknown` instead of a false statement.

### System check

The web interface delivers for every room which sensor drives which output.
This is available as the attribute `system_check` of the firmware entity.

## Dashboard examples

### All rooms with temperature and return flow

```yaml
type: entities
title: Heating
entities:
  - entity: climate.controme_connect_galerie
  - type: sensor
    entity: sensor.controme_connect_galerie_return
  - type: sensor
    entity: sensor.controme_connect_galerie_deviation
```

### Only the rooms with a problem

```yaml
type: entities
title: Heating warning
entities:
  - type: sensor
    entity: binary_sensor.controme_connect_firmware_update
    name: Firmware update available
  - type: sensor
    entity: binary_sensor.controme_connect_galerie_transmission_problem
    name: Galerie
  - type: sensor
    entity: binary_sensor.controme_connect_toni_transmission_problem
    name: Toni
```

### Card with the room temperature

```yaml
type: tile
entity: sensor.controme_connect_galerie_temperature
name: Galerie
vertical: true
features_position: bottom
color: blue
```

## Frequently asked questions

**Why do all humidity sensors show `unknown`?**
Because no humidity sensor is installed in the rooms. As soon as one is
retrofitted, the value appears automatically – the entity already exists.

**Why are the offsets of the modules missing?**
Because they currently do not affect the room. As soon as a module becomes
active, the entity appears.

**The system has several houses.**
During the setup the different house IDs are offered as a choice. If the system
is switched later, that is done under *Reconfigure*.

**Can I control the heating from Home Assistant?**
Yes, the climate entities allow setting the target temperature.

**What happens if the system fails?**
The entities switch to `unavailable`, the log names the reason in a single
line, and the values are back with the next successful request. The firmware
check keeps running in the background, unaffected by this.

## Troubleshooting

| Message | Cause and remedy |
|---|---|
| *Controme system not reachable* | The IP address is wrong or the system does not answer. Check the network connection and the address. |
| *User name or password is invalid* | The web interface rejects the data. Log in to the web interface and set a new password there. |
| *No rooms visible* | The house ID is wrong. Choose a different ID under *Reconfigure*. |
| *Firmware update reports `unknown`* | The web interface is not reachable or the login fails. `update_status` of the firmware entity names the reason. |
| *Transmission problem stays on* | A sensor does not report for too long. `stale_sensors` of the entity names the sensor. |

## Limitations

- The data endpoints of the Controme API are not authenticated. The access
  data are only needed for the login to the web interface.
- For rooms without a sensor the API delivers placeholder texts, the affected
  entities then show `unknown`.
- The deviation (current to target) is only delivered by the API for rooms
  with a flow temperature correction.
- History and statistics are in the local recorder of Home Assistant and are
  not carried over when the integration is switched.
- A firmware update itself has to be triggered in the web interface of the
  system, the integration only reports it.

## Publishing

The repository is hosted on GitHub under
[acki1989/homeassistant-controme-connect](https://github.com/acki1989/homeassistant-controme-connect)
and can be installed via HACS.

### Installation via HACS

1. In HACS add *Settings → Custom repositories*:

   | Field | Value |
   |---|---|
   | Repository | `https://github.com/acki1989/homeassistant-controme-connect` |
   | Category | Integration |

2. Search for **Controme Connect** and download it.
3. Restart Home Assistant.

### Installation without HACS

```bash
git clone https://github.com/acki1989/homeassistant-controme-connect.git
cd homeassistant-controme-connect
./install.sh          # copies to /config/custom_components
```

Restart Home Assistant afterwards.

### Working on it yourself

```bash
cd /config/homeassistant-controme-connect
git pull              # take over the changes of the repository
```

Every push triggers the GitHub Actions check *Validate* (hassfest), which
reports problems in the manifest, the translations or the code.

## Contributing

Bug reports and improvements are welcome – please report them as an
[issue](https://github.com/acki1989/homeassistant-controme-connect/issues).
Please submit code changes as a pull request.

```
custom_components/controme_connect/
├── __init__.py         setup, hub device, platform registration
├── const.py            constants, icon mapping, timeouts
├── coordinator.py      API retrieval, background update check
├── sensor.py           room sensors, deviation, transmission, offsets, firmware
├── binary_sensor.py    transmission problems, firmware update
├── climate.py          heating entities with room icon
├── config_flow.py      setup, house selection, reconfigure
├── firmware.py         login, version query, system check, house detection
└── helpers.py          names, humidity, icons, network scan
```

The integration needs no additional Python dependencies and runs completely in
the local network.

### Tests

The pure helper functions are covered by unit tests:

```bash
pip install pytest aiohttp
python -m pytest tests/
```

## Acknowledgements

- **flame4ever** for the original
  [homeassistant-controme-integration](https://github.com/flame4ever/homeassistant-controme-integration)
- **Controme** for the documented
  [Smart-Heat-OS API](https://support.controme.com/api/)

## Trademarks and logos

**Controme** and **Smart-Heat-OS** are trademarks of Controme GmbH. This
integration is not affiliated with, endorsed by or supported by Controme.
The Controme logo is not used in this repository; the product is only named
to describe the compatibility.

**Home Assistant** and the Home Assistant logo are trademarks of the Open
Home Foundation. They appear here only to indicate compatibility, not to
suggest an official partnership.

The icon and logo of this integration (`brand/icon.png`, `brand/logo.png`)
are self-made graphics, created with `tools/create_brand_images.py`.

## License

MIT – see [LICENSE](LICENSE). The original integration is licensed under the
MIT license of *flame4ever*, this version is a further development based on it.
