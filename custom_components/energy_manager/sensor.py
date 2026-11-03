"""Capteurs : puissance disponible, état des charges, durées de fonctionnement."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import LOAD_POOL, LOAD_WATER_HEATER, LOADS
from .coordinator import EnergyData, EnergyManagerConfigEntry, EnergyManagerCoordinator
from .engine import REASONS
from .entity import EnergyManagerEntity


@dataclass(frozen=True, kw_only=True)
class EnergySensorDescription(SensorEntityDescription):
    """Description d'un capteur calculé à partir de EnergyData."""

    value_fn: Callable[[EnergyData], float | str | None]
    load: str | None = None  # capteur créé seulement si la charge est configurée


def _minutes(values: dict[str, float], key: str) -> float | None:
    return round(values[key] / 60) if key in values else None


def _status(key: str) -> Callable[[EnergyData], str | None]:
    def value(data: EnergyData) -> str | None:
        decision = data.decisions.get(key)
        return decision.reason if decision else None

    return value


POWER = {
    "device_class": SensorDeviceClass.POWER,
    "state_class": SensorStateClass.MEASUREMENT,
    "native_unit_of_measurement": UnitOfPower.WATT,
}
DURATION = {
    "device_class": SensorDeviceClass.DURATION,
    "native_unit_of_measurement": UnitOfTime.MINUTES,
}
STATUS = {"device_class": SensorDeviceClass.ENUM, "options": REASONS}

SENSORS = [
    EnergySensorDescription(
        key="grid_power", value_fn=lambda d: d.grid_power, **POWER
    ),
    EnergySensorDescription(
        key="available_power", value_fn=lambda d: d.available_power, **POWER
    ),
    *(
        EnergySensorDescription(
            key=f"{load}_status", load=load, value_fn=_status(load), **STATUS
        )
        for load in LOADS
    ),
    EnergySensorDescription(
        key="water_heater_runtime",
        load=LOAD_WATER_HEATER,
        value_fn=lambda d: _minutes(d.runtime_s, LOAD_WATER_HEATER),
        **DURATION,
    ),
    EnergySensorDescription(
        key="pool_runtime",
        load=LOAD_POOL,
        value_fn=lambda d: _minutes(d.runtime_s, LOAD_POOL),
        **DURATION,
    ),
    EnergySensorDescription(
        key="pool_required",
        load=LOAD_POOL,
        value_fn=lambda d: _minutes(d.required_s, LOAD_POOL),
        **DURATION,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnergyManagerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        EnergySensor(coordinator, description)
        for description in SENSORS
        if description.load is None or description.load in coordinator.configured_loads
    )


class EnergySensor(EnergyManagerEntity, SensorEntity):
    """Capteur du gestionnaire d'énergie."""

    entity_description: EnergySensorDescription

    def __init__(
        self, coordinator: EnergyManagerCoordinator, description: EnergySensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | str | None:
        return self.entity_description.value_fn(self.coordinator.data)
