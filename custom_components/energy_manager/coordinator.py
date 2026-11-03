"""Coordinateur : lit les mesures, exécute le moteur et pilote les équipements."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
import logging
from typing import Any

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    APP_ENTITY,
    APP_KEY,
    APP_NAME,
    APP_POWER,
    APP_POWER_SENSOR,
    AUTO_MASTER,
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
    LOAD_CLIMATE,
    LOAD_POOL,
    LOAD_WATER_HEATER,
    LOADS,
    UPDATE_INTERVAL,
    WH_IDLE_DELAY,
    WH_IDLE_POWER,
)
from .engine import (
    CLIMATE_KEEP_FRACTION,
    CLIMATE_START_FRACTION,
    PRIORITY,
    REASON_COMFORT,
    REASON_INACTIVE,
    REASON_MANUAL,
    REASON_SURPLUS,
    SEASON_AUTO,
    SEASON_WINTER,
    Appliance,
    Decision,
    Load,
    Tariff,
    available_power,
    clamp,
    cycle_bounds,
    decide,
    estimate_consumption,
    in_window,
    pool_required_hours,
    season_for,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
SWITCH_CONF = {LOAD_WATER_HEATER: CONF_WH_SWITCH, LOAD_POOL: CONF_POOL_SWITCH}
LOAD_CONF = {**SWITCH_CONF, LOAD_CLIMATE: CONF_CLIMATE}
ACTIVE_ACTIONS = (HVACAction.HEATING, HVACAction.COOLING)
DAY_KEYS = ("import_kwh", "export_kwh", "self_kwh", "cost", "savings")

type EnergyManagerConfigEntry = ConfigEntry[EnergyManagerCoordinator]


@dataclass
class EnergyData:
    """Instantané publié aux entités."""

    production: float | None = None
    consumption: float | None = None
    consumption_estimated: bool = False
    appliances_power: float = 0.0
    appliance_power: dict[str, float] = field(default_factory=dict)
    grid_power: float | None = None
    grid_estimated: bool = False
    available_power: float | None = None
    in_offpeak: bool = False
    price: float = 0.0
    rentable_fraction: float = 0.0
    season: str = SEASON_WINTER
    indoor_temperature: float | None = None
    decisions: dict[str, Decision] = field(default_factory=dict)
    runtime_s: dict[str, float] = field(default_factory=dict)
    required_s: dict[str, float] = field(default_factory=dict)
    day: dict[str, float] = field(default_factory=dict)


class EnergyManagerCoordinator(DataUpdateCoordinator[EnergyData]):
    """Boucle de régulation exécutée toutes les UPDATE_INTERVAL."""

    config_entry: EnergyManagerConfigEntry

    def __init__(self, hass: HomeAssistant, entry: EnergyManagerConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.conf: dict[str, Any] = {**DEFAULTS, **(entry.options or entry.data)}
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._state: dict[str, Any] = {
            "cycle": None,
            "runtime": {},
            "done": {},
            "day": dict.fromkeys(DAY_KEYS, 0.0),
            "climate_base": None,
            "climate_target": None,
            "season": SEASON_AUTO,
            "auto": {AUTO_MASTER: True, **dict.fromkeys(LOADS, True)},
        }
        self._observed: dict[str, tuple[bool, datetime]] = {}
        self._last_tick: datetime | None = None
        self._wh_idle_since: datetime | None = None

    @property
    def configured_loads(self) -> list[str]:
        """Charges renseignées dans la configuration."""
        return [key for key in LOADS if self.conf.get(LOAD_CONF[key])]

    @property
    def appliances(self) -> list[dict[str, Any]]:
        return self.conf.get(CONF_APPLIANCES) or []

    async def async_load(self) -> None:
        """Recharge compteurs et consigne d'origine après un redémarrage."""
        if (stored := await self._store.async_load()) is not None:
            self._state["auto"].update(stored.pop("auto", {}))
            self._state["day"].update(stored.pop("day", {}))
            self._state.update(stored)

    @property
    def auto(self) -> dict[str, bool]:
        """Pilotage automatique : global (AUTO_MASTER) et par charge."""
        return self._state["auto"]

    async def async_set_auto(self, key: str, enabled: bool) -> None:
        """Active/désactive le pilotage automatique, puis réévalue aussitôt."""
        self.auto[key] = enabled
        self._store.async_delay_save(lambda: self._state, 1)
        await self.async_request_refresh()

    @property
    def season_mode(self) -> str:
        return self._state["season"]

    async def async_set_season(self, mode: str) -> None:
        self._state["season"] = mode
        self._store.async_delay_save(lambda: self._state, 1)
        await self.async_request_refresh()

    async def async_stop(self) -> None:
        """Rend la main proprement : restaure la consigne clim et sauvegarde."""
        if self._state["climate_target"] is not None:
            await self._set_climate_boost(False, self._climate_state())
        await self._store.async_save(self._state)

    async def _async_update_data(self) -> EnergyData:
        conf = self.conf
        now = dt_util.now()
        offpeak_start = _parse_time(conf[CONF_OFFPEAK_START])
        offpeak_end = _parse_time(conf[CONF_OFFPEAK_END])

        # Le cycle journalier se termine à la fin des heures creuses, pour que
        # le rattrapage nocturne complète la journée solaire qui précède.
        cycle_start, cycle_end = cycle_bounds(now, offpeak_end)
        if self._state["cycle"] != cycle_start.isoformat():
            self._state.update(
                cycle=cycle_start.isoformat(),
                runtime={},
                done={},
                day=dict.fromkeys(DAY_KEYS, 0.0),
            )
            self._wh_idle_since = None

        elapsed = 0.0
        if self._last_tick is not None:
            elapsed = min((now - self._last_tick).total_seconds(), 300.0)
        self._last_tick = now

        tariff = self._tariff()
        data = EnergyData(
            in_offpeak=conf[CONF_OFFPEAK_ENABLED]
            and in_window(now.time(), offpeak_start, offpeak_end),
            rentable_fraction=tariff.rentable_fraction,
            season=season_for(now.month, self.season_mode),
            day=dict(self._state["day"]),
        )
        data.price = tariff.price(data.in_offpeak)

        # --- Charges pilotées et mesures ---------------------------------
        loads: dict[str, Load] = {}
        managed_consumption = 0.0
        if conf.get(CONF_WH_SWITCH):
            if load := self._water_heater_load(now, elapsed, data):
                loads[LOAD_WATER_HEATER] = load
                managed_consumption += load.current_power
        if conf.get(CONF_POOL_SWITCH):
            if load := self._pool_load(now, elapsed, data):
                loads[LOAD_POOL] = load
                managed_consumption += load.current_power
        if conf.get(CONF_CLIMATE):
            climate_power, load = self._climate_load(now, data)
            managed_consumption += climate_power
            if load:
                loads[LOAD_CLIMATE] = load

        appliances = self._appliances()
        data.appliance_power = {a.key: a.power for a in appliances}
        data.appliances_power = sum(data.appliance_power.values()) + managed_consumption

        if conf.get(CONF_SOLAR_POWER):
            data.production = self._read_power(conf[CONF_SOLAR_POWER]) or 0.0
        data.consumption = self._read_power(conf.get(CONF_HOUSE_POWER))
        if data.consumption is None:
            data.consumption = estimate_consumption(conf[CONF_BASELINE], appliances)
            data.consumption += managed_consumption
            data.consumption_estimated = True

        data.grid_power = self._grid_power()
        if data.grid_power is None:
            data.grid_power = data.consumption - (data.production or 0.0)
            data.grid_estimated = True

        # --- Décision ----------------------------------------------------
        managed: list[Load] = []
        for key in PRIORITY[data.season]:
            if key not in self.configured_loads:
                continue
            load = loads.get(key)
            if load is None:
                data.decisions.setdefault(key, Decision(False, REASON_INACTIVE))
            elif not (self.auto[AUTO_MASTER] and self.auto[key]):
                data.decisions[key] = Decision(load.is_on, REASON_MANUAL)
            else:
                managed.append(load)

        data.available_power = available_power(data.grid_power, managed)
        data.decisions.update(
            decide(
                managed,
                data.available_power,
                in_offpeak=data.in_offpeak,
                seconds_left_in_cycle=(cycle_end - now).total_seconds(),
                rentable_fraction=tariff.rentable_fraction,
                margin=conf[CONF_MARGIN],
                max_import=conf[CONF_MAX_IMPORT],
            )
        )

        for load in managed:
            decision = data.decisions[load.key]
            if decision.on != load.is_on and await self._apply(load.key, decision.on):
                self._observed[load.key] = (decision.on, now)

        await self._enforce_comfort(data, LOAD_CLIMATE in {l.key for l in managed})

        # --- Bilan du jour -----------------------------------------------
        self._account(elapsed, data, tariff)
        data.day = dict(self._state["day"])

        self._store.async_delay_save(lambda: self._state, 30)
        return data

    # --- Mesures -----------------------------------------------------------

    def _state_of(self, entity_id: str | None) -> State | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        return state

    def _read_float(self, entity_id: str | None) -> float | None:
        state = self._state_of(entity_id)
        if state is None:
            return None
        try:
            return float(state.state)
        except ValueError:
            return None

    def _read_power(self, entity_id: str | None) -> float | None:
        """Lit un capteur de puissance et le convertit en W."""
        state = self._state_of(entity_id)
        value = self._read_float(entity_id)
        if state is None or value is None:
            return None
        if state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.KILO_WATT:
            value *= 1000
        return value

    def _tariff(self) -> Tariff:
        """Prix du moment : capteurs (Tempo…) s'ils sont renseignés, sinon fixes."""
        conf = self.conf
        peak = self._read_float(conf.get(CONF_PRICE_PEAK_SENSOR))
        offpeak = self._read_float(conf.get(CONF_PRICE_OFFPEAK_SENSOR))
        return Tariff(
            peak=conf[CONF_PRICE_PEAK] if peak is None else peak,
            offpeak=conf[CONF_PRICE_OFFPEAK] if offpeak is None else offpeak,
            export=conf[CONF_PRICE_EXPORT],
        )

    def _grid_power(self) -> float | None:
        """Puissance réseau mesurée (> 0 = import), None si indisponible."""
        conf = self.conf
        if not conf.get(CONF_GRID_POWER):
            return None
        value = self._read_power(conf[CONF_GRID_POWER])
        if value is not None and conf[CONF_GRID_INVERT]:
            value = -value
        return value

    def _is_active(self, state: State | None) -> bool | None:
        """Un appareil consomme-t-il ? None si on ne peut pas le savoir."""
        if state is None:
            return None
        if state.domain == CLIMATE_DOMAIN:
            if (action := state.attributes.get(ATTR_HVAC_ACTION)) is not None:
                return action in ACTIVE_ACTIONS
            return state.state != STATE_OFF
        return state.state == STATE_ON

    def _appliances(self) -> list[Appliance]:
        result = []
        for app in self.appliances:
            result.append(
                Appliance(
                    key=app[APP_KEY],
                    name=app[APP_NAME],
                    nominal=float(app.get(APP_POWER) or 0),
                    is_on=self._is_active(self._state_of(app.get(APP_ENTITY))),
                    measured=self._read_power(app.get(APP_POWER_SENSOR)),
                )
            )
        return result

    def _since_change(self, key: str, is_on: bool, now: datetime) -> float:
        """Secondes depuis le dernier changement d'état observé."""
        previous = self._observed.get(key)
        if previous is None:
            # Premier passage : on n'impose pas d'anti court-cycle.
            self._observed[key] = (is_on, now - timedelta(days=1))
        elif previous[0] != is_on:
            self._observed[key] = (is_on, now)
        return (now - self._observed[key][1]).total_seconds()

    def _switch_load(
        self, key: str, now: datetime, nominal: float, power_conf: str
    ) -> tuple[Load, float | None] | None:
        state = self._state_of(self.conf[SWITCH_CONF[key]])
        if state is None:
            return None
        is_on = state.state == STATE_ON
        measured = self._read_power(self.conf.get(power_conf))
        current = (measured if measured is not None else nominal) if is_on else 0.0
        load = Load(
            key=key,
            nominal_power=nominal,
            current_power=current,
            is_on=is_on,
            seconds_since_change=self._since_change(key, is_on, now),
            min_on_s=self.conf[CONF_MIN_ON] * 60,
            min_off_s=self.conf[CONF_MIN_OFF] * 60,
        )
        return load, measured

    def _add_runtime(self, key: str, seconds: float) -> float:
        runtime = self._state["runtime"].get(key, 0.0) + seconds
        self._state["runtime"][key] = runtime
        return runtime

    def _water_heater_load(
        self, now: datetime, elapsed: float, data: EnergyData
    ) -> Load | None:
        result = self._switch_load(
            LOAD_WATER_HEATER, now, self.conf[CONF_WH_NOMINAL], CONF_WH_POWER
        )
        if result is None:
            return None
        load, measured = result
        heating = load.is_on and (measured is None or measured > WH_IDLE_POWER)
        runtime = self._add_runtime(LOAD_WATER_HEATER, elapsed if heating else 0.0)

        # Alimenté mais ne consomme plus : le thermostat a coupé, ballon chaud.
        if load.is_on and measured is not None and measured <= WH_IDLE_POWER:
            self._wh_idle_since = self._wh_idle_since or now
            if now - self._wh_idle_since >= WH_IDLE_DELAY:
                self._state["done"][LOAD_WATER_HEATER] = True
        else:
            self._wh_idle_since = None

        required = self.conf[CONF_WH_MIN_HOURS] * 3600
        load.done = self._state["done"].get(LOAD_WATER_HEATER, False)
        load.remaining_s = 0.0 if load.done else max(0.0, required - runtime)
        data.runtime_s[LOAD_WATER_HEATER] = runtime
        data.required_s[LOAD_WATER_HEATER] = required
        return load

    def _pool_load(self, now: datetime, elapsed: float, data: EnergyData) -> Load | None:
        result = self._switch_load(
            LOAD_POOL, now, self.conf[CONF_POOL_NOMINAL], CONF_POOL_POWER
        )
        if result is None:
            return None
        load, _ = result
        runtime = self._add_runtime(LOAD_POOL, elapsed if load.is_on else 0.0)
        required = 3600 * pool_required_hours(
            self._read_float(self.conf.get(CONF_POOL_TEMP)),
            self.conf[CONF_POOL_HOURS],
            self.conf[CONF_POOL_MIN_HOURS],
            self.conf[CONF_POOL_MAX_HOURS],
        )
        load.remaining_s = max(0.0, required - runtime)
        load.done = load.remaining_s == 0
        data.runtime_s[LOAD_POOL] = runtime
        data.required_s[LOAD_POOL] = required
        return load

    # --- Clim / chauffage --------------------------------------------------

    def _climate_state(self) -> State | None:
        return self._state_of(self.conf[CONF_CLIMATE])

    def _comfort_band(self, season: str) -> tuple[float, float]:
        conf = self.conf
        if season == SEASON_WINTER:
            return conf[CONF_WINTER_MIN], conf[CONF_WINTER_MAX]
        return conf[CONF_SUMMER_MIN], conf[CONF_SUMMER_MAX]

    def _climate_mode_ok(self, state: State, season: str) -> bool:
        """En hiver on ne pilote que le chauffage, en été que la clim."""
        expected = HVACMode.HEAT if season == SEASON_WINTER else HVACMode.COOL
        return state.state == expected

    def _indoor_temperature(self, state: State | None) -> float | None:
        if (value := self._read_float(self.conf.get(CONF_INDOOR_TEMP))) is not None:
            return value
        if state is None:
            return None
        try:
            return float(state.attributes[ATTR_CURRENT_TEMPERATURE])
        except (KeyError, TypeError, ValueError):
            return None

    def _climate_load(
        self, now: datetime, data: EnergyData
    ) -> tuple[float, Load | None]:
        """Retourne (puissance consommée actuellement, charge « boost » ou None).

        Le boost est vu comme une charge on/off : consigne portée au bout de la
        bande de confort tant que le solaire le couvre.
        """
        state = self._climate_state()
        measured = self._read_power(self.conf.get(CONF_CLIMATE_POWER_SENSOR))
        nominal = self.conf[CONF_CLIMATE_POWER]
        active = self._is_active(state)
        consumption = measured if measured is not None else (nominal if active else 0.0)
        data.indoor_temperature = self._indoor_temperature(state)

        if state is None or not self._climate_mode_ok(state, data.season):
            return consumption, None
        setpoint = state.attributes.get(ATTR_TEMPERATURE)
        if setpoint is None:
            return consumption, None

        target = self._state["climate_target"]
        if target is not None and abs(float(setpoint) - target) > 0.25:
            # Consigne modifiée à la main pendant le boost : on la respecte.
            _LOGGER.debug("Consigne clim modifiée manuellement, boost abandonné")
            self._state.update(climate_base=None, climate_target=None)
            target = None
        boosting = target is not None
        return consumption, Load(
            key=LOAD_CLIMATE,
            nominal_power=nominal,
            current_power=(measured if measured is not None else nominal)
            if boosting
            else 0.0,
            is_on=boosting,
            seconds_since_change=self._since_change(LOAD_CLIMATE, boosting, now),
            min_on_s=self.conf[CONF_MIN_ON] * 60,
            min_off_s=self.conf[CONF_MIN_OFF] * 60,
            start_fraction=CLIMATE_START_FRACTION,
            keep_fraction=CLIMATE_KEEP_FRACTION,
        )

    async def _enforce_comfort(self, data: EnergyData, managed: bool) -> None:
        """Maintient la consigne dans la bande de confort hors boost, et
        marque « confort » quand la température est hors bande."""
        state = self._climate_state()
        if self._state["climate_target"] is not None and not managed:
            # Boost actif alors que la clim n'est plus pilotée : on restaure.
            await self._set_climate_boost(False, state)
            return
        if not managed or state is None or self._state["climate_target"] is not None:
            return

        low, high = self._comfort_band(data.season)
        setpoint = state.attributes.get(ATTR_TEMPERATURE)
        if setpoint is not None and (wanted := clamp(float(setpoint), low, high)) != float(
            setpoint
        ):
            await self._call(
                CLIMATE_DOMAIN,
                SERVICE_SET_TEMPERATURE,
                {ATTR_ENTITY_ID: state.entity_id, ATTR_TEMPERATURE: wanted},
            )

        temp = data.indoor_temperature
        decision = data.decisions.get(LOAD_CLIMATE)
        if temp is not None and decision and decision.reason != REASON_SURPLUS:
            cold = data.season == SEASON_WINTER and temp < low
            hot = data.season != SEASON_WINTER and temp > high
            if cold or hot:
                data.decisions[LOAD_CLIMATE] = Decision(decision.on, REASON_COMFORT)

    # --- Actions -----------------------------------------------------------

    async def _call(self, domain: str, service: str, data: dict[str, Any]) -> bool:
        try:
            await self.hass.services.async_call(domain, service, data, blocking=True)
        except HomeAssistantError as err:
            _LOGGER.warning("Échec de %s.%s sur %s : %s", domain, service, data, err)
            return False
        return True

    async def _apply(self, key: str, on: bool) -> bool:
        if key == LOAD_CLIMATE:
            return await self._set_climate_boost(on, self._climate_state())
        _LOGGER.debug("%s -> %s", key, "on" if on else "off")
        return await self._call(
            "homeassistant",
            SERVICE_TURN_ON if on else SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: self.conf[SWITCH_CONF[key]]},
        )

    async def _set_climate_boost(self, on: bool, state: State | None) -> bool:
        if state is None:
            if not on:
                self._state.update(climate_base=None, climate_target=None)
            return False

        season = season_for(dt_util.now().month, self.season_mode)
        low, high = self._comfort_band(season)
        if on:
            base = clamp(float(state.attributes[ATTR_TEMPERATURE]), low, high)
            # Chauffer jusqu'au haut de la bande en hiver, refroidir jusqu'au
            # bas en été : on stocke l'énergie solaire dans la maison.
            target = high if season == SEASON_WINTER else low
            target = clamp(
                target,
                state.attributes.get(ATTR_MIN_TEMP, target),
                state.attributes.get(ATTR_MAX_TEMP, target),
            )
            if target == base:
                return False
        else:
            base, target = self._state["climate_base"], None
            if base is None:
                self._state["climate_target"] = None
                return True
            base = clamp(base, low, high)

        ok = await self._call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_TEMPERATURE: target if on else base},
        )
        if ok or not on:
            self._state.update(
                climate_base=base if on else None, climate_target=target if on else None
            )
        return ok

    # --- Bilan -------------------------------------------------------------

    def _account(self, elapsed: float, data: EnergyData, tariff: Tariff) -> None:
        """Cumule import/export/autoconsommation et leur valeur en €."""
        if elapsed <= 0 or data.grid_power is None or data.consumption is None:
            return
        hours = elapsed / 3600
        day = self._state["day"]
        imported = max(0.0, data.grid_power) * hours / 1000
        exported = max(0.0, -data.grid_power) * hours / 1000
        produced = (data.production or 0.0) * hours / 1000
        day["import_kwh"] += imported
        day["export_kwh"] += exported
        day["self_kwh"] += max(0.0, produced - exported)
        day["cost"] += imported * data.price - exported * tariff.export
        day["savings"] += max(0.0, produced - exported) * data.price


def _parse_time(value: str) -> time:
    return dt_util.parse_time(value) or time(0)
