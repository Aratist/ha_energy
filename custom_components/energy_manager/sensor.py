"""Capteurs : mesures, tarifs, état des charges, bilan du jour, appareils."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import APP_KEY, APP_NAME, LOAD_POOL, LOAD_WATER_HEATER, LOADS
from .coordinator import EnergyData, EnergyManagerConfigEntry, EnergyManagerCoordinator
from .engine import REASONS, SEASON_SUMMER, SEASON_WINTER
from .entity import EnergyManagerEntity


@dataclass(frozen=True, kw_only=True)
class EnergySensorDescription(SensorEntityDescription):
    """Description d'un capteur calculé à partir de EnergyData."""

    value_fn: Callable[[EnergyData], float | str | None]
    attrs_fn: Callable[[EnergyData], dict[str, Any]] | None = None
    load: str | None = None  # capteur créé seulement si la charge est configurée


def _minutes(values: dict[str, float], key: str) -> float | None:
    return round(values[key] / 60) if key in values else None


def _status(key: str) -> Callable[[EnergyData], str | None]:
    def value(data: EnergyData) -> str | None:
        decision = data.decisions.get(key)
        return decision.reason if decision else None

    return value


def _day(key: str, digits: int) -> Callable[[EnergyData], float | None]:
    return lambda d: round(d.day[key], digits) if key in d.day else None


POWER = {
    "device_class": SensorDeviceClass.POWER,
    "state_class": SensorStateClass.MEASUREMENT,
    "native_unit_of_measurement": UnitOfPower.WATT,
}
ENERGY = {
    "device_class": SensorDeviceClass.ENERGY,
    "state_class": SensorStateClass.TOTAL_INCREASING,
    "native_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
}
MONEY = {
    "device_class": SensorDeviceClass.MONETARY,
    "native_unit_of_measurement": "EUR",
}
DURATION = {
    "device_class": SensorDeviceClass.DURATION,
    "native_unit_of_measurement": UnitOfTime.MINUTES,
}
STATUS = {"device_class": SensorDeviceClass.ENUM, "options": REASONS}

SENSORS = [
    EnergySensorDescription(
        key="consumption",
        value_fn=lambda d: None if d.consumption is None else round(d.consumption),
        attrs_fn=lambda d: {"source": "estimated" if d.consumption_estimated else "measured"},
        **POWER,
    ),
    EnergySensorDescription(
        key="production", value_fn=lambda d: d.production, **POWER
    ),
    EnergySensorDescription(
        key="grid_power",
        value_fn=lambda d: None if d.grid_power is None else round(d.grid_power),
        attrs_fn=lambda d: {"source": "estimated" if d.grid_estimated else "measured"},
        **POWER,
    ),
    EnergySensorDescription(
        key="available_power",
        value_fn=lambda d: None if d.available_power is None else round(d.available_power),
        **POWER,
    ),
    EnergySensorDescription(
        key="appliances_power", value_fn=lambda d: round(d.appliances_power), **POWER
    ),
    EnergySensorDescription(
        key="tariff",
        value_fn=lambda d: "offpeak" if d.in_offpeak else "peak",
        device_class=SensorDeviceClass.ENUM,
        options=["peak", "offpeak"],
    ),
    EnergySensorDescription(
        key="price",
        value_fn=lambda d: round(d.price, 4),
        native_unit_of_measurement="EUR/kWh",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EnergySensorDescription(
        key="rentable_fraction",
        value_fn=lambda d: round(d.rentable_fraction * 100),
        native_unit_of_measurement=PERCENTAGE,
    ),
    EnergySensorDescription(
        key="season",
        value_fn=lambda d: d.season,
        device_class=SensorDeviceClass.ENUM,
        options=[SEASON_WINTER, SEASON_SUMMER],
    ),
    EnergySensorDescription(
        key="indoor_temperature",
        load="climate",
        value_fn=lambda d: d.indoor_temperature,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EnergySensorDescription(key="import_today", value_fn=_day("import_kwh", 2), **ENERGY),
    EnergySensorDescription(key="export_today", value_fn=_day("export_kwh", 2), **ENERGY),
    EnergySensorDescription(
        key="self_consumption_today", value_fn=_day("self_kwh", 2), **ENERGY
    ),
    EnergySensorDescription(key="cost_today", value_fn=_day("cost", 2), **MONEY),
    EnergySensorDescription(key="savings_today", value_fn=_day("savings", 2), **MONEY),
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
    entities: list[SensorEntity] = [
        EnergySensor(coordinator, description)
        for description in SENSORS
        if description.load is None or description.load in coordinator.configured_loads
    ]
    entities.extend(
        ApplianceSensor(coordinator, app[APP_KEY], app[APP_NAME])
        for app in coordinator.appliances
    )
    async_add_entities(entities)


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

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)


class ApplianceSensor(EnergyManagerEntity, SensorEntity):
    """Puissance mesurée ou estimée d'un appareil configuré."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_translation_key = "appliance_power"

    def __init__(
        self, coordinator: EnergyManagerCoordinator, key: str, name: str
    ) -> None:
        super().__init__(coordinator, f"appliance_{key}")
        self._key = key
        self._attr_translation_placeholders = {"name": name}

    @property
    def native_value(self) -> float | None:
        value = self.coordinator.data.appliance_power.get(self._key)
        return None if value is None else round(value)
