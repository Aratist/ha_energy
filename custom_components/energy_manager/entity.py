"""Entité de base rattachée à l'appareil « Gestionnaire d'énergie »."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EnergyManagerCoordinator


class EnergyManagerEntity(CoordinatorEntity[EnergyManagerCoordinator]):
    """Entité du gestionnaire d'énergie."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EnergyManagerCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Gestionnaire d'énergie",
            entry_type=DeviceEntryType.SERVICE,
        )
