"""The Controme integration."""
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
    """Set up the Controme component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Controme from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    coordinator = ContromeDataUpdateCoordinator(
        hass,
        entry.data[CONF_API_URL],
        entry.data[CONF_HAUS_ID],
        entry.data.get(CONF_USER, ""),
        entry.data.get(CONF_PASSWORD, ""),
    )

    await coordinator.async_config_entry_first_refresh()

    # Register the main Controme hub device. The room devices are attached to
    # it, so its device id is needed for them.
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
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        # Stop the coordinator, otherwise it would keep polling the API
        data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if data:
            await data["coordinator"].async_shutdown()
            hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded