"""Assistant de configuration (création et options).

Étapes : mesures → équipements → appareils (menu) → tarifs → confort → réglages.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TimeSelector,
)
from homeassistant.util import slugify

from .const import (
    APP_ENTITY,
    APP_KEY,
    APP_NAME,
    APP_POWER,
    APP_POWER_SENSOR,
    APPLIANCE_DOMAINS,
    CONF_APPLIANCES,
    CONF_BASELINE,
    CONF_CLIMATE,
    CONF_CLIMATE_POWER,
    CONF_CLIMATE_POWER_SENSOR,
    CONF_GRID_INVERT,
    CONF_GRID_POWER,
    CONF_HOUSE_POWER,
    CONF_INDOOR_TEMP,
    CONF_MARGIN,
    CONF_MAX_IMPORT,
    CONF_MIN_OFF,
    CONF_MIN_ON,
    CONF_OFFPEAK_ENABLED,
    CONF_OFFPEAK_END,
    CONF_OFFPEAK_START,
    CONF_POOL_HOURS,
    CONF_POOL_MAX_HOURS,
    CONF_POOL_MIN_HOURS,
    CONF_POOL_NOMINAL,
    CONF_POOL_POWER,
    CONF_POOL_SWITCH,
    CONF_POOL_TEMP,
    CONF_PRICE_EXPORT,
    CONF_PRICE_OFFPEAK,
    CONF_PRICE_OFFPEAK_SENSOR,
    CONF_PRICE_PEAK,
    CONF_PRICE_PEAK_SENSOR,
    CONF_SOLAR_POWER,
    CONF_SUMMER_MAX,
    CONF_SUMMER_MIN,
    CONF_WH_MIN_HOURS,
    CONF_WH_NOMINAL,
    CONF_WH_POWER,
    CONF_WH_SWITCH,
    CONF_WINTER_MAX,
    CONF_WINTER_MIN,
    DEFAULTS,
    DOMAIN,
)

POWER_SENSOR = EntitySelector(
    EntitySelectorConfig(domain="sensor", device_class="power")
)
TEMP_SENSOR = EntitySelector(
    EntitySelectorConfig(domain="sensor", device_class="temperature")
)
ANY_SENSOR = EntitySelector(EntitySelectorConfig(domain="sensor"))
ON_OFF = EntitySelector(EntitySelectorConfig(domain=["switch", "input_boolean"]))
CLIMATE = EntitySelector(EntitySelectorConfig(domain="climate"))
APPLIANCE = EntitySelector(EntitySelectorConfig(domain=APPLIANCE_DOMAINS))


def _number(min_: float, max_: float, step: float | str, unit: str) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=min_, max=max_, step=step, unit_of_measurement=unit,
            mode=NumberSelectorMode.BOX,
        )
    )


SOURCES_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_GRID_POWER): POWER_SENSOR,
        vol.Optional(CONF_GRID_INVERT): BooleanSelector(),
        vol.Optional(CONF_SOLAR_POWER): POWER_SENSOR,
        vol.Optional(CONF_HOUSE_POWER): POWER_SENSOR,
        vol.Required(CONF_BASELINE): _number(0, 3000, 10, "W"),
    }
)

LOADS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_WH_SWITCH): ON_OFF,
        vol.Optional(CONF_WH_POWER): POWER_SENSOR,
        vol.Optional(CONF_POOL_SWITCH): ON_OFF,
        vol.Optional(CONF_POOL_POWER): POWER_SENSOR,
        vol.Optional(CONF_POOL_TEMP): TEMP_SENSOR,
        vol.Optional(CONF_CLIMATE): CLIMATE,
        vol.Optional(CONF_CLIMATE_POWER_SENSOR): POWER_SENSOR,
        vol.Optional(CONF_INDOOR_TEMP): TEMP_SENSOR,
    }
)

APPLIANCE_SCHEMA = vol.Schema(
    {
        vol.Required(APP_NAME): TextSelector(),
        vol.Optional(APP_ENTITY): APPLIANCE,
        vol.Required(APP_POWER, default=0): _number(0, 10000, 10, "W"),
        vol.Optional(APP_POWER_SENSOR): POWER_SENSOR,
    }
)

TARIFF_SCHEMA = vol.Schema(
    {
        # HA impose un pas ≥ 0,001 ; « any » laisse saisir 4 décimales.
        vol.Required(CONF_PRICE_PEAK): _number(0, 2, "any", "€/kWh"),
        vol.Required(CONF_PRICE_OFFPEAK): _number(0, 2, "any", "€/kWh"),
        vol.Required(CONF_PRICE_EXPORT): _number(0, 2, "any", "€/kWh"),
        vol.Optional(CONF_PRICE_PEAK_SENSOR): ANY_SENSOR,
        vol.Optional(CONF_PRICE_OFFPEAK_SENSOR): ANY_SENSOR,
        vol.Required(CONF_OFFPEAK_ENABLED): BooleanSelector(),
        vol.Required(CONF_OFFPEAK_START): TimeSelector(),
        vol.Required(CONF_OFFPEAK_END): TimeSelector(),
    }
)

COMFORT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_WINTER_MIN): _number(10, 30, 0.5, "°C"),
        vol.Required(CONF_WINTER_MAX): _number(10, 30, 0.5, "°C"),
        vol.Required(CONF_SUMMER_MIN): _number(15, 35, 0.5, "°C"),
        vol.Required(CONF_SUMMER_MAX): _number(15, 35, 0.5, "°C"),
    }
)

SETTINGS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_WH_NOMINAL): _number(100, 6000, 50, "W"),
        vol.Required(CONF_WH_MIN_HOURS): _number(0, 12, 0.5, "h"),
        vol.Required(CONF_POOL_NOMINAL): _number(100, 5000, 50, "W"),
        vol.Required(CONF_POOL_HOURS): _number(0, 24, 0.5, "h"),
        vol.Required(CONF_POOL_MIN_HOURS): _number(0, 24, 0.5, "h"),
        vol.Required(CONF_POOL_MAX_HOURS): _number(0, 24, 0.5, "h"),
        vol.Required(CONF_CLIMATE_POWER): _number(100, 10000, 50, "W"),
        vol.Required(CONF_MARGIN): _number(0, 2000, 10, "W"),
        vol.Required(CONF_MAX_IMPORT): _number(0, 3000, 10, "W"),
        vol.Required(CONF_MIN_ON): _number(0, 120, 1, "min"),
        vol.Required(CONF_MIN_OFF): _number(0, 120, 1, "min"),
    }
)


def _validate_sources(user_input: dict[str, Any]) -> dict[str, str]:
    if user_input.get(CONF_GRID_POWER) or user_input.get(CONF_HOUSE_POWER):
        return {}
    if user_input.get(CONF_SOLAR_POWER):
        return {}  # consommation estimée à partir des appareils
    return {"base": "no_power_source"}


def _validate_loads(user_input: dict[str, Any]) -> dict[str, str]:
    if any(user_input.get(k) for k in (CONF_WH_SWITCH, CONF_POOL_SWITCH, CONF_CLIMATE)):
        return {}
    return {"base": "no_load"}


def _validate_appliance(user_input: dict[str, Any]) -> dict[str, str]:
    if not user_input.get(APP_ENTITY) and not user_input.get(APP_POWER_SENSOR):
        return {"base": "appliance_no_source"}
    if user_input.get(APP_ENTITY) and not user_input.get(APP_POWER_SENSOR):
        if not user_input.get(APP_POWER):
            return {APP_POWER: "appliance_no_power"}
    return {}


def _validate_tariff(user_input: dict[str, Any]) -> dict[str, str]:
    if user_input[CONF_PRICE_OFFPEAK] > user_input[CONF_PRICE_PEAK]:
        return {CONF_PRICE_OFFPEAK: "offpeak_above_peak"}
    if user_input.get(CONF_PRICE_EXPORT, 0) >= user_input[CONF_PRICE_PEAK]:
        return {CONF_PRICE_EXPORT: "export_above_peak"}
    return {}


def _validate_comfort(user_input: dict[str, Any]) -> dict[str, str]:
    if user_input[CONF_WINTER_MIN] >= user_input[CONF_WINTER_MAX]:
        return {CONF_WINTER_MAX: "band_inverted"}
    if user_input[CONF_SUMMER_MIN] >= user_input[CONF_SUMMER_MAX]:
        return {CONF_SUMMER_MAX: "band_inverted"}
    return {}


class _Steps:
    """Étapes communes à la création et aux options.

    Chaque étape remplace entièrement ses propres clés : un champ optionnel
    vidé par l'utilisateur disparaît donc bien de la configuration.
    """

    _data: dict[str, Any]

    def _merge(self, schema: vol.Schema, user_input: dict[str, Any]) -> None:
        for key in schema.schema:
            self._data.pop(str(key), None)
        self._data.update(user_input)

    async def _step(
        self,
        step_id: str,
        schema: vol.Schema,
        user_input: dict[str, Any] | None,
        validate,
        next_step,
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = validate(user_input) if validate else {}
            if not errors:
                self._merge(schema, user_input)
                return await next_step()
        return self.async_show_form(  # type: ignore[attr-defined]
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(  # type: ignore[attr-defined]
                schema, user_input or self._data
            ),
            errors=errors,
        )

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        return await self._step(
            "user", SOURCES_SCHEMA, user_input, _validate_sources, self.async_step_loads
        )

    async def async_step_loads(self, user_input=None) -> ConfigFlowResult:
        return await self._step(
            "loads", LOADS_SCHEMA, user_input, _validate_loads, self.async_step_appliances
        )

    # --- Appareils : menu ajouter / supprimer / continuer -------------------

    async def async_step_appliances(self, user_input=None) -> ConfigFlowResult:
        options = ["add_appliance"]
        if self._data.get(CONF_APPLIANCES):
            options.append("remove_appliance")
        options.append("tariff")
        names = ", ".join(a[APP_NAME] for a in self._data.get(CONF_APPLIANCES, []))
        return self.async_show_menu(  # type: ignore[attr-defined]
            step_id="appliances",
            menu_options=options,
            description_placeholders={"appliances": names or "—"},
        )

    async def async_step_add_appliance(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_appliance(user_input)
            if not errors:
                apps = list(self._data.get(CONF_APPLIANCES, []))
                key = base = slugify(user_input[APP_NAME]) or "appareil"
                existing = {a[APP_KEY] for a in apps}
                i = 2
                while key in existing:
                    key, i = f"{base}_{i}", i + 1
                apps.append({APP_KEY: key, **user_input})
                self._data[CONF_APPLIANCES] = apps
                return await self.async_step_appliances()
        return self.async_show_form(  # type: ignore[attr-defined]
            step_id="add_appliance",
            data_schema=self.add_suggested_values_to_schema(  # type: ignore[attr-defined]
                APPLIANCE_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_remove_appliance(self, user_input=None) -> ConfigFlowResult:
        apps = list(self._data.get(CONF_APPLIANCES, []))
        if user_input is not None:
            removed = set(user_input.get("remove", []))
            self._data[CONF_APPLIANCES] = [a for a in apps if a[APP_KEY] not in removed]
            return await self.async_step_appliances()
        options = [SelectOptionDict(value=a[APP_KEY], label=a[APP_NAME]) for a in apps]
        return self.async_show_form(  # type: ignore[attr-defined]
            step_id="remove_appliance",
            data_schema=vol.Schema(
                {
                    vol.Optional("remove", default=[]): SelectSelector(
                        SelectSelectorConfig(options=options, multiple=True)
                    )
                }
            ),
        )

    async def async_step_tariff(self, user_input=None) -> ConfigFlowResult:
        return await self._step(
            "tariff", TARIFF_SCHEMA, user_input, _validate_tariff, self.async_step_comfort
        )

    async def async_step_comfort(self, user_input=None) -> ConfigFlowResult:
        return await self._step(
            "comfort", COMFORT_SCHEMA, user_input, _validate_comfort, self.async_step_settings
        )

    async def async_step_settings(self, user_input=None) -> ConfigFlowResult:
        return await self._step(
            "settings", SETTINGS_SCHEMA, user_input, None, self._finish
        )

    async def _finish(self) -> ConfigFlowResult:
        raise NotImplementedError


class EnergyManagerConfigFlow(_Steps, ConfigFlow, domain=DOMAIN):
    """Création de l'intégration (une seule instance par maison)."""

    VERSION = 1

    def __init__(self) -> None:
        self._data = dict(DEFAULTS)

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return await super().async_step_user(user_input)

    async def _finish(self) -> ConfigFlowResult:
        return self.async_create_entry(title="Gestionnaire d'énergie", data=self._data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> EnergyManagerOptionsFlow:
        return EnergyManagerOptionsFlow()


class EnergyManagerOptionsFlow(_Steps, OptionsFlow):
    """Modification de tous les réglages après installation."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        self._data = {
            **DEFAULTS,
            **(self.config_entry.options or self.config_entry.data),
        }
        return await self.async_step_user()

    async def _finish(self) -> ConfigFlowResult:
        return self.async_create_entry(data=self._data)
