"""Sélecteur de saison : automatique (selon le mois), hiver ou été."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import EnergyManagerConfigEntry, EnergyManagerCoordinator
from .engine import SEASONS
from .entity import EnergyManagerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnergyManagerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([SeasonSelect(entry.runtime_data)])


class SeasonSelect(EnergyManagerEntity, SelectEntity):
    """La saison inverse la priorité entre chauffage et piscine."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = SEASONS

    def __init__(self, coordinator: EnergyManagerCoordinator) -> None:
        super().__init__(coordinator, "season_mode")

    @property
    def current_option(self) -> str:
        return self.coordinator.season_mode

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_season(option)
        self.async_write_ha_state()
