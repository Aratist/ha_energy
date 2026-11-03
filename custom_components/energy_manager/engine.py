"""Moteur de décision pur (aucun import Home Assistant, testable unitairement).

Convention de signe : puissance réseau > 0 = soutirage (import),
puissance réseau < 0 = injection (export de surplus solaire).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

REASON_SURPLUS = "surplus"  # en marche grâce au surplus solaire
REASON_FORCED = "forced"  # en marche forcée (heures creuses / fin de cycle)
REASON_DONE = "done"  # objectif atteint pour le cycle
REASON_WAITING = "waiting"  # à l'arrêt, en attente de surplus
REASON_HOLD = "hold"  # état maintenu (anti court-cycle)
REASON_MANUAL = "manual"  # pilotage automatique désactivé
REASON_INACTIVE = "inactive"  # équipement indisponible / non éligible

REASONS = [
    REASON_SURPLUS,
    REASON_FORCED,
    REASON_DONE,
    REASON_WAITING,
    REASON_HOLD,
    REASON_MANUAL,
    REASON_INACTIVE,
]


@dataclass
class Load:
    """Charge pilotable telle que vue par le moteur."""

    key: str
    nominal_power: float  # W consommés quand la charge démarre
    current_power: float  # W consommés actuellement (0 si arrêtée)
    is_on: bool
    seconds_since_change: float
    min_on_s: float = 0.0
    min_off_s: float = 0.0
    remaining_s: float = 0.0  # durée garantie restant due sur le cycle
    done: bool = False


@dataclass
class Decision:
    """Décision du moteur pour une charge."""

    on: bool
    reason: str


def in_window(now: time, start: time, end: time) -> bool:
    """Indique si `now` est dans la plage [start, end[, minuit compris."""
    if start == end:
        return False
    if start < end:
        return start <= now < end
    return now >= start or now < end


def cycle_bounds(now: datetime, reset: time) -> tuple[datetime, datetime]:
    """Bornes du cycle journalier courant, qui commence chaque jour à `reset`."""
    start = now.replace(
        hour=reset.hour, minute=reset.minute, second=reset.second, microsecond=0
    )
    if start > now:
        start -= timedelta(days=1)
    return start, start + timedelta(days=1)


def available_power(grid_power: float | None, loads: list[Load]) -> float | None:
    """Puissance disponible si aucune charge pilotée ne tournait."""
    if grid_power is None:
        return None
    return -grid_power + sum(load.current_power for load in loads if load.is_on)


def decide(
    loads: list[Load],
    available: float | None,
    *,
    in_offpeak: bool,
    seconds_left_in_cycle: float,
    margin: float,
    max_import: float,
) -> dict[str, Decision]:
    """Répartit la puissance disponible entre les charges.

    `loads` est trié par priorité décroissante. Les charges en marche forcée
    sont servies en premier, puis le surplus est attribué dans l'ordre.
    Une charge déjà en marche est conservée tant que le déficit reste
    inférieur à `max_import` (hystérésis).
    """
    budget = None if available is None else available - margin
    decisions: dict[str, Decision] = {}

    def must_run(load: Load) -> bool:
        return (
            not load.done
            and load.remaining_s > 0
            and (in_offpeak or load.remaining_s >= seconds_left_in_cycle)
        )

    ordered = [l for l in loads if must_run(l)] + [l for l in loads if not must_run(l)]

    for load in ordered:
        if load.done:
            want, reason = False, REASON_DONE
        elif must_run(load):
            want, reason = True, REASON_FORCED
        elif budget is None:
            want, reason = False, REASON_WAITING
        elif load.is_on:
            want = budget >= load.current_power - max_import
            reason = REASON_SURPLUS if want else REASON_WAITING
        else:
            want = budget >= load.nominal_power
            reason = REASON_SURPLUS if want else REASON_WAITING

        if want != load.is_on:
            min_s = load.min_on_s if load.is_on else load.min_off_s
            if load.seconds_since_change < min_s:
                want, reason = load.is_on, REASON_HOLD

        if want and budget is not None:
            budget -= load.current_power if load.is_on else load.nominal_power

        decisions[load.key] = Decision(want, reason)

    return decisions


def pool_required_hours(
    water_temp: float | None, fixed_hours: float, min_hours: float, max_hours: float
) -> float:
    """Durée de filtration : règle « température / 2 », sinon durée fixe."""
    if water_temp is None:
        return fixed_hours
    return max(min_hours, min(max_hours, water_temp / 2))
