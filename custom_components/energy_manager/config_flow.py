"""Assistant de configuration (création et options) en trois étapes."""

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
    TimeSelector,
)

from .const import (
    CONF_CLIMATE,
    CONF_CLIMATE_OFFSET,
    CONF_CLIMATE_POWER,
    CONF_GRID_INVERT,
    CONF_GRID_POWER,
    CONF_HOUSE_POWER,
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
    CONF_SOLAR_POWER,
    CONF_WH_MIN_HOURS,
    CONF_WH_NOMINAL,
    CONF_WH_POWER,
    CONF_WH_SWITCH,
    DEFAULTS,
    DOMAIN,
)

POWER_SENSOR = EntitySelector(
    EntitySelectorConfig(domain="sensor", device_class="power")
)
TEMP_SENSOR = EntitySelector(
    EntitySelectorConfig(domain="sensor", device_class="temperature")
)
ON_OFF = EntitySelector(EntitySelectorConfig(domain=["switch", "input_boolean"]))
CLIMATE = EntitySelector(EntitySelectorConfig(domain="climate"))


def _number(min_: float, max_: float, step: float, unit: str) -> NumberSelector:
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
        vol.Required(CONF_CLIMATE_OFFSET): _number(0.5, 5, 0.5, "°C"),
        vol.Required(CONF_OFFPEAK_ENABLED): BooleanSelector(),
        vol.Required(CONF_OFFPEAK_START): TimeSelector(),
        vol.Required(CONF_OFFPEAK_END): TimeSelector(),
        vol.Required(CONF_MARGIN): _number(0, 2000, 10, "W"),
        vol.Required(CONF_MAX_IMPORT): _number(0, 3000, 10, "W"),
        vol.Required(CONF_MIN_ON): _number(0, 120, 1, "min"),
        vol.Required(CONF_MIN_OFF): _number(0, 120, 1, "min"),
    }
)


def _validate_sources(user_input: dict[str, Any]) -> dict[str, str]:
    if user_input.get(CONF_GRID_POWER) or user_input.get(CONF_HOUSE_POWER):
        return {}
    return {"base": "no_power_source"}


def _validate_loads(user_input: dict[str, Any]) -> dict[str, str]:
    if any(user_input.get(k) for k in (CONF_WH_SWITCH, CONF_POOL_SWITCH, CONF_CLIMATE)):
        return {}
    return {"base": "no_load"}


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
            "loads", LOADS_SCHEMA, user_input, _validate_loads, self.async_step_settings
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
