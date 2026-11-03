"""Gestionnaire d'énergie solaire : chauffe-eau, piscine et clim/chauffage."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import APP_KEY
from .coordinator import EnergyManagerConfigEntry, EnergyManagerCoordinator

PLATFORMS = [Platform.SELECT, Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: EnergyManagerConfigEntry) -> bool:
    """Démarre la boucle de régulation."""
    coordinator = EnergyManagerCoordinator(hass, entry)
    await coordinator.async_load()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    _remove_stale_appliances(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EnergyManagerConfigEntry) -> bool:
    """Arrête la régulation et rend la main sur les équipements."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_stop()
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: EnergyManagerConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _remove_stale_appliances(
    hass: HomeAssistant, entry: EnergyManagerConfigEntry, coordinator: EnergyManagerCoordinator
) -> None:
    """Supprime les capteurs des appareils retirés de la configuration."""
    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_appliance_"
    keep = {f"{prefix}{app[APP_KEY]}" for app in coordinator.appliances}
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg_entry.unique_id.startswith(prefix) and reg_entry.unique_id not in keep:
            registry.async_remove(reg_entry.entity_id)
