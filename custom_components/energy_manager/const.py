"""Constantes du gestionnaire d'énergie."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "energy_manager"
UPDATE_INTERVAL = timedelta(seconds=30)

# Charges pilotées
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
CONF_BASELINE = "baseline_power"  # talon de la maison pour l'estimation

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
CONF_CLIMATE_POWER_SENSOR = "climate_power_sensor"
CONF_CLIMATE_POWER = "climate_boost_power"
CONF_INDOOR_TEMP = "indoor_temperature"

# Appareils mesurés ou estimés (liste de dictionnaires)
CONF_APPLIANCES = "appliances"
APP_KEY = "key"
APP_NAME = "name"
APP_ENTITY = "entity"
APP_POWER = "power"
APP_POWER_SENSOR = "power_sensor"
APPLIANCE_DOMAINS = [
    "switch",
    "light",
    "fan",
    "climate",
    "water_heater",
    "media_player",
    "input_boolean",
    "binary_sensor",
]

# Tarifs
CONF_PRICE_PEAK = "price_peak"
CONF_PRICE_OFFPEAK = "price_offpeak"
CONF_PRICE_EXPORT = "price_export"
CONF_PRICE_PEAK_SENSOR = "price_peak_sensor"
CONF_PRICE_OFFPEAK_SENSOR = "price_offpeak_sensor"
CONF_OFFPEAK_ENABLED = "offpeak_enabled"
CONF_OFFPEAK_START = "offpeak_start"
CONF_OFFPEAK_END = "offpeak_end"

# Confort
CONF_WINTER_MIN = "winter_min"
CONF_WINTER_MAX = "winter_max"
CONF_SUMMER_MIN = "summer_min"
CONF_SUMMER_MAX = "summer_max"

# Paramètres généraux
CONF_MARGIN = "margin"
CONF_MAX_IMPORT = "max_import"
CONF_MIN_ON = "min_on_minutes"
CONF_MIN_OFF = "min_off_minutes"

DEFAULTS = {
    CONF_GRID_INVERT: False,
    CONF_BASELINE: 250,
    CONF_APPLIANCES: [],
    CONF_WH_NOMINAL: 2000,
    CONF_WH_MIN_HOURS: 3,
    CONF_POOL_NOMINAL: 800,
    CONF_POOL_HOURS: 6,
    CONF_POOL_MIN_HOURS: 2,
    CONF_POOL_MAX_HOURS: 14,
    CONF_CLIMATE_POWER: 1000,
    CONF_PRICE_PEAK: 0.2146,
    CONF_PRICE_OFFPEAK: 0.1696,
    CONF_PRICE_EXPORT: 0.0,
    CONF_OFFPEAK_ENABLED: True,
    CONF_OFFPEAK_START: "22:00:00",
    CONF_OFFPEAK_END: "06:00:00",
    CONF_WINTER_MIN: 19.0,
    CONF_WINTER_MAX: 23.0,
    CONF_SUMMER_MIN: 24.0,
    CONF_SUMMER_MAX: 27.0,
    CONF_MARGIN: 100,
    CONF_MAX_IMPORT: 300,
    CONF_MIN_ON: 10,
    CONF_MIN_OFF: 5,
}

# Détection « ballon chaud » : puissance mesurée sous ce seuil pendant ce délai
WH_IDLE_POWER = 50
WH_IDLE_DELAY = timedelta(minutes=10)
