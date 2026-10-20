# Controme Connect

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io)
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

The full documentation is available in German:
[README.md](README.md).

---

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
   | Repository | `https://github.com/<your-user>/homeassistant-controme-connect` |
   | Category | Integration |

2. Search for **Controme Connect** in HACS and download it.
3. Restart Home Assistant.

### Manual

Copy the folder `custom_components/controme_connect` from this repository into
the Home Assistant configuration directory (`/config/custom_components/`) and
restart Home Assistant.

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
| **House ID** | Number of the house within the system, usually `1`. |
| **User** | User of the Controme web interface |
| **Password** | Password of the Controme web interface |

## Entities

The IDs contain the room name of the system, e.g. `Galerie` → `galerie`.

### Per room

| Entity ID | Name |
|---|---|
| `sensor.controme_connect_<room>_temperature` | Temperature |
| `sensor.controme_connect_<room>_target` | Target temperature |
| `sensor.controme_connect_<room>_mode` | Operating mode |
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

### System

| Entity ID | Name |
|---|---|
| `sensor.controme_connect_firmware` | Firmware |
| `binary_sensor.controme_connect_firmware_update` | Firmware update available |

## Notes

- **Only effective modules are visible.** A system provides about nine offset
  modules, most of them permanently at zero. A module only gets an entity when
  it actually affects the room. If it becomes active later (for example the
  weather correction in winter), the integration reloads itself and the entity
  appears.
- **Different timeouts.** The solar powered room thermostats sleep between
  transmissions and get a timeout of 6 hours, all other sensors 30 minutes.
- **Return flow temperatures.** The system abbreviates them as `RL`
  (e.g. `Galerie RL`); `RL`, `Rücklauf` and `Ruecklauf` are all recognised.
- **Firmware and updates.** The API does not expose any update information, the
  web interface does. The check runs in the background every six hours and can
  never block the room sensors. The beta version is reported separately and
  never triggers an update hint.

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

MIT – see [LICENSE](LICENSE).
