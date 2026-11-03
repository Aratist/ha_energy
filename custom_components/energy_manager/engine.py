"""Moteur de décision pur (aucun import Home Assistant, testable unitairement).

Convention de signe : puissance réseau > 0 = soutirage (import),
puissance réseau < 0 = injection (export de surplus solaire).

Principe d'optimisation du coût : un appareil différable (chauffe-eau,
piscine) ne démarre en heures pleines que si le surplus solaire couvre au
moins la « part rentable » de sa puissance, c'est-à-dire la part à partir de
laquelle le démarrer maintenant ne coûte pas plus cher que de l'attendre en
heures creuses. Sinon il est rattrapé pendant les heures creuses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from .const import LOAD_CLIMATE, LOAD_POOL, LOAD_WATER_HEATER

REASON_SURPLUS = "surplus"  # en marche grâce au solaire (rentable)
REASON_FORCED = "forced"  # en marche forcée (heures creuses / fin de cycle)
REASON_COMFORT = "comfort"  # chauffage/clim nécessaire au confort (hors bande)
REASON_DONE = "done"  # objectif atteint pour le cycle
REASON_WAITING = "waiting"  # à l'arrêt, en attente de surplus
REASON_HOLD = "hold"  # état maintenu (anti court-cycle)
REASON_MANUAL = "manual"  # pilotage automatique désactivé
REASON_INACTIVE = "inactive"  # équipement indisponible / non éligible

REASONS = [
    REASON_SURPLUS,
    REASON_FORCED,
    REASON_COMFORT,
    REASON_DONE,
    REASON_WAITING,
    REASON_HOLD,
    REASON_MANUAL,
    REASON_INACTIVE,
]

SEASON_AUTO = "auto"
SEASON_WINTER = "winter"
SEASON_SUMMER = "summer"
SEASONS = [SEASON_AUTO, SEASON_WINTER, SEASON_SUMMER]
WINTER_MONTHS = {11, 12, 1, 2, 3}

# Ordre de priorité des charges selon la saison : en hiver le chauffage passe
# avant la piscine, en été c'est l'inverse.
PRIORITY = {
    SEASON_WINTER: [LOAD_CLIMATE, LOAD_WATER_HEATER, LOAD_POOL],
    SEASON_SUMMER: [LOAD_WATER_HEATER, LOAD_POOL, LOAD_CLIMATE],
}

# Le « boost » de la clim stocke de la chaleur pour le soir (heures pleines) :
# il n'est rentable que couvert entièrement par le solaire.
CLIMATE_START_FRACTION = 1.0
CLIMATE_KEEP_FRACTION = 0.6


@dataclass(frozen=True)
class Tariff:
    """Prix de l'énergie en €/kWh."""

    peak: float  # heures pleines
    offpeak: float  # heures creuses
    export: float = 0.0  # revente du surplus (0 = surplus perdu)

    def price(self, in_offpeak: bool) -> float:
        return self.offpeak if in_offpeak else self.peak

    @property
    def rentable_fraction(self) -> float:
        """Part de la puissance d'un appareil que le surplus doit couvrir pour
        qu'un démarrage en heures pleines coûte au plus autant qu'en heures
        creuses : (1-f)·HP + f·export ≤ HC  ⇔  f ≥ (HP-HC)/(HP-export)."""
        if self.peak <= self.export:
            return 0.0
        return max(0.0, min(1.0, (self.peak - self.offpeak) / (self.peak - self.export)))


@dataclass
class Appliance:
    """Appareil mesuré ou estimé, pour reconstituer la consommation."""

    key: str
    name: str
    nominal: float  # W consommés quand il est allumé
    is_on: bool | None = None  # None = état inconnu
    measured: float | None = None  # W mesurés si un capteur existe

    @property
    def power(self) -> float:
        if self.measured is not None:
            return self.measured
        return self.nominal if self.is_on else 0.0


def estimate_consumption(baseline: float, appliances: list[Appliance]) -> float:
    """Consommation estimée : talon de la maison + appareils connus."""
    return baseline + sum(a.power for a in appliances)


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
    start_fraction: float | None = None  # part solaire requise (None = tarif)
    keep_fraction: float | None = None  # part solaire pour rester en marche


@dataclass
class Decision:
    """Décision du moteur pour une charge."""

    on: bool
    reason: str


def season_for(month: int, mode: str) -> str:
    """Saison effective : forcée, ou déduite du mois (nov. à mars = hiver)."""
    if mode in (SEASON_WINTER, SEASON_SUMMER):
        return mode
    return SEASON_WINTER if month in WINTER_MONTHS else SEASON_SUMMER


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
    rentable_fraction: float,
    margin: float,
    max_import: float,
) -> dict[str, Decision]:
    """Répartit la puissance disponible entre les charges.

    `loads` est trié par priorité décroissante. Les charges en marche forcée
    sont servies en premier, puis le surplus est attribué dans l'ordre.
    Une charge démarre si le surplus couvre sa part rentable ; une charge déjà
    en marche est conservée tant que le déficit reste inférieur à
    `max_import` (hystérésis).
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
        else:
            start = rentable_fraction if load.start_fraction is None else load.start_fraction
            keep = start if load.keep_fraction is None else load.keep_fraction
            if load.is_on:
                want = budget >= keep * load.current_power - max_import
            else:
                want = budget >= start * load.nominal_power
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


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
