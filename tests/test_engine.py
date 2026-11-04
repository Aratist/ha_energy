"""Tests du moteur de décision (sans Home Assistant)."""

from datetime import date, datetime, time
import importlib.util
from pathlib import Path
import sys
import types

# engine.py est chargé directement : le paquet importe Home Assistant.
_DIR = Path(__file__).parents[1] / "custom_components/energy_manager"


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(f"energy_manager.{name}", _DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"energy_manager.{name}"] = module
    spec.loader.exec_module(module)
    return module


sys.modules.setdefault("energy_manager", types.ModuleType("energy_manager"))
const = _load("const", "const.py")
engine = _load("engine", "engine.py")

Load = engine.Load
Tariff = engine.Tariff


def load(key, nominal=1000, *, on=False, current=None, since=3600, **kw):
    return Load(
        key=key,
        nominal_power=nominal,
        current_power=(nominal if current is None else current) if on else 0.0,
        is_on=on,
        seconds_since_change=since,
        min_on_s=600,
        min_off_s=300,
        **kw,
    )


def run(loads, grid, *, offpeak=False, left=12 * 3600, k=1.0, margin=100, max_import=300):
    available = engine.available_power(grid, loads)
    return engine.decide(
        loads,
        available,
        in_offpeak=offpeak,
        seconds_left_in_cycle=left,
        rentable_fraction=k,
        margin=margin,
        max_import=max_import,
    )


# --- Tarifs ---------------------------------------------------------------


def test_rentable_fraction_without_export():
    # 1 - HC/HP : exactement la règle « part solaire minimale rentable »
    assert Tariff(peak=0.2146, offpeak=0.1696).rentable_fraction == (
        (0.2146 - 0.1696) / 0.2146
    )


def test_rentable_fraction_with_export_is_higher():
    without = Tariff(0.25, 0.20).rentable_fraction
    with_export = Tariff(0.25, 0.20, export=0.10).rentable_fraction
    assert with_export > without
    assert Tariff(0.25, 0.25).rentable_fraction == 0.0


def test_rentable_fraction_never_when_export_pays_more_than_peak():
    # Vendre rapporte plus que consommer : on attend les heures creuses.
    assert Tariff(0.10, 0.05, export=0.20).rentable_fraction == 1.0
    assert Tariff(0.10, 0.05, export=0.10).rentable_fraction == 1.0


def test_price_by_period():
    tariff = Tariff(0.25, 0.20)
    assert tariff.price(False) == 0.25 and tariff.price(True) == 0.20


# --- Répartition ----------------------------------------------------------


def test_surplus_allocated_by_priority():
    loads = [load("wh", 2000), load("pool", 800), load("clim", 1000)]
    d = run(loads, grid=-3000)  # 3 kW injectés, 2,9 kW utilisables
    assert d["wh"].on and d["pool"].on and not d["clim"].on
    assert d["clim"].reason == engine.REASON_WAITING


def test_partial_coverage_starts_when_rentable():
    # k = 25 % : 500 W de surplus suffisent à lancer un chauffe-eau de 2 kW
    loads = [load("wh", 2000)]
    assert not run(loads, grid=-550, k=1.0)["wh"].on
    assert run(loads, grid=-650, k=0.25)["wh"].on


def test_load_specific_fraction_overrides_tariff():
    # Le boost clim exige une couverture complète même si le tarif est permissif
    loads = [load("clim", 1000, start_fraction=1.0, keep_fraction=0.6)]
    assert not run(loads, grid=-600, k=0.25)["clim"].on
    assert run(loads, grid=-1200, k=0.25)["clim"].on


def test_keep_fraction_hysteresis():
    loads = [load("clim", 1000, on=True, start_fraction=1.0, keep_fraction=0.6)]
    # 1 kW consommé, 300 W importés : 700 W couverts ≥ 600 W → on garde
    assert run(loads, grid=300, max_import=0)["clim"].on
    assert not run(loads, grid=500, max_import=0)["clim"].on


def test_running_load_kept_within_max_import():
    loads = [load("wh", 2000, on=True)]
    assert run(loads, grid=200)["wh"].on
    assert not run(loads, grid=800)["wh"].on


def test_anti_short_cycle_holds_state():
    loads = [load("wh", 2000, on=True, since=60)]
    d = run(loads, grid=1500)
    assert d["wh"].on and d["wh"].reason == engine.REASON_HOLD

    loads = [load("pool", 800, since=60)]
    d = run(loads, grid=-2000)
    assert not d["pool"].on and d["pool"].reason == engine.REASON_HOLD


def test_forced_in_offpeak_when_runtime_missing():
    loads = [load("wh", 2000, remaining_s=3600)]
    d = run(loads, grid=500, offpeak=True)
    assert d["wh"].on and d["wh"].reason == engine.REASON_FORCED


def test_forced_when_cycle_ends_soon_without_offpeak():
    loads = [load("pool", 800, remaining_s=2 * 3600)]
    assert not run(loads, grid=500, left=3 * 3600)["pool"].on
    assert run(loads, grid=500, left=2 * 3600)["pool"].on


def test_forced_load_consumes_budget_first():
    loads = [load("wh", 2000), load("pool", 800, remaining_s=3600)]
    d = run(loads, grid=-2500, offpeak=True)
    assert d["pool"].reason == engine.REASON_FORCED
    assert not d["wh"].on


def test_done_load_is_stopped():
    loads = [load("wh", 2000, on=True, current=0, done=True)]
    d = run(loads, grid=-3000)
    assert not d["wh"].on and d["wh"].reason == engine.REASON_DONE


def test_missing_measurement_keeps_surplus_loads_off():
    assert not run([load("pool", 800)], grid=None)["pool"].on


# --- Estimation de la consommation ----------------------------------------


def test_estimate_consumption():
    apps = [
        engine.Appliance("a", "Four", nominal=2000, is_on=True),
        engine.Appliance("b", "Lave-linge", nominal=1500, is_on=False),
        engine.Appliance("c", "Jacuzzi", nominal=0, is_on=None, measured=2126),
        engine.Appliance("d", "Inconnu", nominal=500, is_on=None),
    ]
    assert engine.estimate_consumption(250, apps) == 250 + 2000 + 2126


# --- Saisons ----------------------------------------------------------------


def test_season_auto_and_forced():
    assert engine.season_for(1, engine.SEASON_AUTO) == engine.SEASON_WINTER
    assert engine.season_for(7, engine.SEASON_AUTO) == engine.SEASON_SUMMER
    assert engine.season_for(1, engine.SEASON_SUMMER) == engine.SEASON_SUMMER


def test_priority_swaps_climate_and_pool():
    winter, summer = engine.PRIORITY[engine.SEASON_WINTER], engine.PRIORITY[engine.SEASON_SUMMER]
    assert winter.index(const.LOAD_CLIMATE) < winter.index(const.LOAD_POOL)
    assert summer.index(const.LOAD_POOL) < summer.index(const.LOAD_CLIMATE)
    assert set(winter) == set(summer) == set(const.LOADS)


# --- Utilitaires ------------------------------------------------------------


def test_in_window_across_midnight():
    assert engine.in_window(time(23), time(22), time(6))
    assert engine.in_window(time(3), time(22), time(6))
    assert not engine.in_window(time(12), time(22), time(6))
    assert engine.in_window(time(13), time(12), time(14))
    assert not engine.in_window(time(13), time(6), time(6))


def test_cycle_bounds():
    start, end = engine.cycle_bounds(datetime(2026, 7, 1, 3, 0), time(6))
    assert start == datetime(2026, 6, 30, 6, 0) and end == datetime(2026, 7, 1, 6, 0)
    start, _ = engine.cycle_bounds(datetime(2026, 7, 1, 7, 0), time(6))
    assert start == datetime(2026, 7, 1, 6, 0)


def test_period_start_week_is_iso_monday():
    # Mercredi 4 novembre 2026 → lundi 2 novembre
    assert engine.period_start(date(2026, 11, 4), "week") == date(2026, 11, 2)
    # Un lundi est son propre début de semaine ; un dimanche remonte 6 jours.
    assert engine.period_start(date(2026, 11, 2), "week") == date(2026, 11, 2)
    assert engine.period_start(date(2026, 11, 8), "week") == date(2026, 11, 2)
    # Semaine à cheval sur deux mois : 1er août 2026 (samedi) → lundi 27 juillet
    assert engine.period_start(date(2026, 8, 1), "week") == date(2026, 7, 27)
    # Semaine à cheval sur deux années : 1er janvier 2027 (vendredi) → 28 déc. 2026
    assert engine.period_start(date(2027, 1, 1), "week") == date(2026, 12, 28)


def test_period_start_month_and_year():
    assert engine.period_start(date(2026, 11, 30), "month") == date(2026, 11, 1)
    assert engine.period_start(date(2026, 12, 31), "year") == date(2026, 1, 1)
    assert engine.period_start(date(2027, 1, 1), "month") == date(2027, 1, 1)
    assert engine.period_start(date(2027, 1, 1), "year") == date(2027, 1, 1)
    # Année bissextile
    assert engine.period_start(date(2028, 2, 29), "month") == date(2028, 2, 1)


def test_period_start_accepts_datetime_and_rejects_unknown_period():
    assert engine.period_start(datetime(2026, 11, 4, 23, 59), "week") == date(2026, 11, 2)
    assert type(engine.period_start(datetime(2026, 11, 4), "month")) is date
    try:
        engine.period_start(date(2026, 11, 4), "decade")
    except ValueError:
        pass
    else:
        raise AssertionError("période inconnue acceptée")


def test_pool_required_hours():
    assert engine.pool_required_hours(None, 6, 2, 14) == 6
    assert engine.pool_required_hours(24, 6, 2, 14) == 12
    assert engine.pool_required_hours(32, 6, 2, 14) == 14
    assert engine.pool_required_hours(2, 6, 2, 14) == 2


def test_clamp():
    assert engine.clamp(17, 19, 23) == 19
    assert engine.clamp(25, 19, 23) == 23
    assert engine.clamp(21, 19, 23) == 21
