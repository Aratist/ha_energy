"""Constantes du gestionnaire d'énergie."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "energy_manager"
UPDATE_INTERVAL = timedelta(seconds=30)

# Charges pilotées (l'ordre définit la priorité)
LOAD_WATER_HEATER = "water_heater"
LOAD_POOL = "pool"
LOAD_CLIMATE = "climate"
LOADS = [LOAD_WATER_HEATER, LOAD_POOL, LOAD_CLIMATE]
AUTO_MASTER = "master"

# Sources de mesure
CONF_GRID_POWER = "grid_power"
CONF_GRID_INVERT = "grid_invert"
CONF_SOLAR_POWER = "solar_power"
CONF_HOUSE_POWER = "house_power"

# Chauffe-eau
CONF_WH_SWITCH = "water_heater_switch"
CONF_WH_POWER = "water_heater_power"
CONF_WH_NOMINAL = "water_heater_nominal_power"
CONF_WH_MIN_HOURS = "water_heater_min_hours"

# Piscine
CONF_POOL_SWITCH = "pool_switch"
CONF_POOL_POWER = "pool_power"
CONF_POOL_TEMP = "pool_temperature"
CONF_POOL_NOMINAL = "pool_nominal_power"
CONF_POOL_HOURS = "pool_hours"
CONF_POOL_MIN_HOURS = "pool_min_hours"
CONF_POOL_MAX_HOURS = "pool_max_hours"

# Climatisation / chauffage
CONF_CLIMATE = "climate"
CONF_CLIMATE_POWER = "climate_boost_power"
CONF_CLIMATE_OFFSET = "climate_offset"

# Paramètres généraux
CONF_OFFPEAK_ENABLED = "offpeak_enabled"
CONF_OFFPEAK_START = "offpeak_start"
CONF_OFFPEAK_END = "offpeak_end"
CONF_MARGIN = "margin"
CONF_MAX_IMPORT = "max_import"
CONF_MIN_ON = "min_on_minutes"
CONF_MIN_OFF = "min_off_minutes"

DEFAULTS = {
    CONF_GRID_INVERT: False,
    CONF_WH_NOMINAL: 2000,
    CONF_WH_MIN_HOURS: 3,
    CONF_POOL_NOMINAL: 800,
    CONF_POOL_HOURS: 6,
    CONF_POOL_MIN_HOURS: 2,
    CONF_POOL_MAX_HOURS: 14,
    CONF_CLIMATE_POWER: 1000,
    CONF_CLIMATE_OFFSET: 1.0,
    CONF_OFFPEAK_ENABLED: True,
    CONF_OFFPEAK_START: "22:00:00",
    CONF_OFFPEAK_END: "06:00:00",
    CONF_MARGIN: 100,
    CONF_MAX_IMPORT: 300,
    CONF_MIN_ON: 10,
    CONF_MIN_OFF: 5,
}

# Détection « ballon chaud » : puissance mesurée sous ce seuil pendant ce délai
WH_IDLE_POWER = 50
WH_IDLE_DELAY = timedelta(minutes=10)
