"""Interrupteurs d'activation du pilotage automatique (global et par charge)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import AUTO_MASTER
from .coordinator import EnergyManagerConfigEntry, EnergyManagerCoordinator
from .entity import EnergyManagerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnergyManagerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        AutoSwitch(coordinator, key)
        for key in [AUTO_MASTER, *coordinator.configured_loads]
    )


class AutoSwitch(EnergyManagerEntity, SwitchEntity):
    """Active ou suspend le pilotage automatique ; l'état est persisté.

    Coupé, l'équipement n'est plus touché du tout (pilotage manuel).
    Affiché dans « Contrôles » pour rester à portée de main.
    """

    def __init__(self, coordinator: EnergyManagerCoordinator, key: str) -> None:
        super().__init__(coordinator, f"{key}_auto")
        self._key = key

    @property
    def is_on(self) -> bool:
        return self.coordinator.auto[self._key]

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_auto(self._key, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_auto(self._key, False)
        self.async_write_ha_state()
