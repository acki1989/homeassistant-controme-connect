"""Die Controme-Integration."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from .coordinator import ContromeDataUpdateCoordinator
from .const import DOMAIN, CONF_HAUS_ID, CONF_API_URL, CONF_USER, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.CLIMATE, Platform.BINARY_SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Richtet die Controme-Komponente ein."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Richtet Controme anhand eines Konfigurationseintrags ein."""
    hass.data.setdefault(DOMAIN, {})
    coordinator = ContromeDataUpdateCoordinator(
        hass,
        entry.data[CONF_API_URL],
        entry.data[CONF_HAUS_ID],
        entry.data.get(CONF_USER, ""),
        entry.data.get(CONF_PASSWORD, ""),
    )

    await coordinator.async_config_entry_first_refresh()

    # Hub-Gerät der Anlage registrieren. Die Raum-Geräte sind ihm
    # zugeordnet, dafür wird dessen Geräte-ID benötigt.
    device_registry = dr.async_get(hass)
    hub_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.data[CONF_HAUS_ID])},
        manufacturer="Controme",
        name=f"Controme Home {entry.data[CONF_HAUS_ID]}",
        model="Thermostat API",
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "config": entry.data,
        "hub_device_id": hub_device.id,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Lädt einen Konfigurationseintrag herunter."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        # Coordinator stoppen, sonst fragt er die API weiter ab
        data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if data:
            await data["coordinator"].async_shutdown()
            hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded