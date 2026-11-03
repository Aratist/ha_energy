"""Tests du moteur de décision (sans Home Assistant)."""

from datetime import datetime, time
import importlib.util
from pathlib import Path
import sys

# engine.py est chargé directement : le paquet importe Home Assistant.
_PATH = Path(__file__).parents[1] / "custom_components/energy_manager/engine.py"
_spec = importlib.util.spec_from_file_location("engine", _PATH)
engine = importlib.util.module_from_spec(_spec)
sys.modules["engine"] = engine
_spec.loader.exec_module(engine)

Load = engine.Load


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


def run(loads, grid, *, offpeak=False, left=12 * 3600, margin=100, max_import=300):
    available = engine.available_power(grid, loads)
    return engine.decide(
        loads,
        available,
        in_offpeak=offpeak,
        seconds_left_in_cycle=left,
        margin=margin,
        max_import=max_import,
    )


def test_surplus_allocated_by_priority():
    loads = [load("wh", 2000), load("pool", 800), load("clim", 1000)]
    d = run(loads, grid=-3000)  # 3 kW injectés, 2,9 kW utilisables
    assert d["wh"].on and d["pool"].on and not d["clim"].on
    assert d["clim"].reason == engine.REASON_WAITING


def test_lower_priority_skipped_if_too_big_but_next_fits():
    loads = [load("wh", 2000), load("pool", 800)]
    d = run(loads, grid=-1000)
    assert not d["wh"].on and d["pool"].on


def test_running_load_counts_back_into_available():
    # Le chauffe-eau tourne (2 kW) et on importe 200 W : on le garde (hystérésis).
    loads = [load("wh", 2000, on=True)]
    d = run(loads, grid=200)
    assert d["wh"].on and d["wh"].reason == engine.REASON_SURPLUS


def test_running_load_stopped_when_import_too_high():
    loads = [load("wh", 2000, on=True)]
    d = run(loads, grid=800)
    assert not d["wh"].on


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
    # Piscine forcée (priorité basse) : le chauffe-eau ne démarre pas sur le surplus restant.
    loads = [load("wh", 2000), load("pool", 800, remaining_s=3600)]
    d = run(loads, grid=-2500, offpeak=True)
    assert d["pool"].reason == engine.REASON_FORCED
    assert not d["wh"].on


def test_done_load_is_stopped():
    loads = [load("wh", 2000, on=True, current=0, done=True)]
    d = run(loads, grid=-3000)
    assert not d["wh"].on and d["wh"].reason == engine.REASON_DONE


def test_missing_measurement_keeps_surplus_loads_off():
    loads = [load("pool", 800)]
    d = run(loads, grid=None)
    assert not d["pool"].on


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


def test_pool_required_hours():
    assert engine.pool_required_hours(None, 6, 2, 14) == 6
    assert engine.pool_required_hours(24, 6, 2, 14) == 12
    assert engine.pool_required_hours(32, 6, 2, 14) == 14
    assert engine.pool_required_hours(2, 6, 2, 14) == 2
