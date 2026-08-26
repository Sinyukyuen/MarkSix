"""Generate Mark Six ticket suggestions from scored numbers."""

from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass
from itertools import combinations

from marksix.analysis import NumberStats, balance_score, zone_of

UNIT_BET_HKD = 10
BET_TYPES = ("single", "multiple", "banker")


@dataclass(frozen=True)
class Ticket:
    numbers: tuple[int, ...]
    special: int
    ticket_score: float
    balance: float
    strategy: str


@dataclass(frozen=True)
class MultipleBet:
    """復式: pick N numbers; covers C(N, 6) single units."""

    numbers: tuple[int, ...]
    units: int
    cost_hkd: int
    ticket_score: float
    balance: float
    strategy: str


@dataclass(frozen=True)
class BankerBet:
    """拖膽: bankers (膽) must appear; trailers (拖) fill remaining slots."""

    bankers: tuple[int, ...]
    trailers: tuple[int, ...]
    units: int
    cost_hkd: int
    ticket_score: float
    balance: float
    strategy: str


def _score_lookup(stats: list[NumberStats]) -> dict[int, float]:
    return {item.number: item.composite_score for item in stats}


def _set_score(numbers: list[int], scores: dict[int, float]) -> float:
    return sum(scores.get(number, 0.0) for number in numbers)


def _softmax_weights(values: list[float], temperature: float = 0.55) -> list[float]:
    if not values:
        return []
    scaled = [value / max(temperature, 0.05) for value in values]
    peak = max(scaled)
    exps = [math.exp(value - peak) for value in scaled]
    total = sum(exps) or 1.0
    return [value / total for value in exps]


def _zone_ok(chosen: list[int], candidate: int, max_per_zone: int = 2) -> bool:
    zones = Counter(zone_of(number) for number in chosen)
    return zones[zone_of(candidate)] < max_per_zone


def _diversified_pick(
    pool: list[NumberStats],
    count: int,
    rng: random.Random,
    *,
    temperature: float = 0.55,
    max_per_zone: int = 2,
) -> list[int]:
    available = pool[:]
    chosen: list[int] = []
    while len(chosen) < count and available:
        eligible = [item for item in available if _zone_ok(chosen, item.number, max_per_zone)]
        if not eligible:
            eligible = available
        weights = _softmax_weights(
            [max(item.composite_score, 0.01) for item in eligible],
            temperature=temperature,
        )
        pick = rng.choices(eligible, weights=weights, k=1)[0]
        chosen.append(pick.number)
        available = [item for item in available if item.number != pick.number]
    return sorted(chosen)


def _spread_ticket(stats: list[NumberStats]) -> list[int] | None:
    """One number from each zone where possible, by score."""
    by_zone: dict[int, list[NumberStats]] = {index: [] for index in range(5)}
    for item in stats:
        by_zone[zone_of(item.number)].append(item)

    picked: list[int] = []
    for zone in range(5):
        if by_zone[zone]:
            picked.append(by_zone[zone][0].number)

    if len(picked) >= 6:
        return sorted(picked[:6])

    remaining = [item for item in stats if item.number not in picked]
    for item in remaining:
        if len(picked) == 6:
            break
        if _zone_ok(picked, item.number, max_per_zone=2):
            picked.append(item.number)
    return sorted(picked) if len(picked) == 6 else None


def _pick_special(stats: list[NumberStats], main_numbers: set[int], rng: random.Random) -> int:
    pool = [item for item in stats if item.number not in main_numbers][:20]
    weights = _softmax_weights([max(item.composite_score, 0.01) for item in pool], temperature=0.7)
    return rng.choices(pool, weights=weights, k=1)[0].number


def generate_tickets(
    stats: list[NumberStats],
    *,
    strategy: str,
    count: int = 5,
    seed: int | None = None,
    min_balance: float = 0.50,
) -> list[Ticket]:
    rng = random.Random(seed)
    tickets: list[Ticket] = []
    seen: set[tuple[int, ...]] = set()
    scores = _score_lookup(stats)
    pool = stats[:28]

    # First ticket: zone-spread (less sticky than pure top-6)
    spread = _spread_ticket(stats)
    if spread is not None:
        key = tuple(spread)
        seen.add(key)
        tickets.append(
            Ticket(
                numbers=key,
                special=_pick_special(stats, set(spread), rng),
                ticket_score=_set_score(spread, scores),
                balance=balance_score(spread),
                strategy=strategy,
            )
        )

    temperatures = (0.45, 0.65, 0.85, 1.05, 1.25)
    attempts = 0
    while len(tickets) < count and attempts < count * 300:
        attempts += 1
        temperature = temperatures[(len(tickets) + attempts) % len(temperatures)]
        numbers = _diversified_pick(pool, 6, rng, temperature=temperature)
        if len(numbers) != 6:
            continue
        balance = balance_score(numbers)
        if balance < min_balance:
            continue
        key = tuple(numbers)
        if key in seen:
            continue
        # Prefer tickets that don't heavily overlap earlier ones
        if tickets:
            overlap = max(len(set(key) & set(existing.numbers)) for existing in tickets)
            if overlap >= 4 and rng.random() < 0.7:
                continue
        seen.add(key)
        tickets.append(
            Ticket(
                numbers=key,
                special=_pick_special(stats, set(numbers), rng),
                ticket_score=_set_score(numbers, scores),
                balance=balance,
                strategy=strategy,
            )
        )

    tickets.sort(key=lambda item: (item.balance * 0.35 + item.ticket_score * 0.65), reverse=True)
    return tickets[:count]


def _multiple_units(size: int) -> int:
    return math.comb(size, 6)


def _banker_units(banker_count: int, trailer_count: int) -> int:
    remaining = 6 - banker_count
    if remaining < 0 or trailer_count < remaining:
        raise ValueError("Invalid banker/trailer sizes.")
    return math.comb(trailer_count, remaining)


def _estimate_set_balance(numbers: list[int], pick: int = 6) -> float:
    if len(numbers) <= pick:
        return balance_score(numbers)

    subsets = list(combinations(numbers, pick))
    if len(subsets) > 40:
        step = max(1, len(subsets) // 40)
        subsets = subsets[::step][:40]
    return sum(balance_score(list(subset)) for subset in subsets) / len(subsets)


def _coverage_pool(stats: list[NumberStats], pick_count: int) -> list[int]:
    """Build a diverse pool: mix top scores with zone coverage."""
    picked: list[int] = []
    zone_counts: Counter[int] = Counter()
    for item in stats:
        zone = zone_of(item.number)
        if zone_counts[zone] >= max(2, pick_count // 4 + 1):
            continue
        picked.append(item.number)
        zone_counts[zone] += 1
        if len(picked) == pick_count:
            break
    if len(picked) < pick_count:
        for item in stats:
            if item.number not in picked:
                picked.append(item.number)
            if len(picked) == pick_count:
                break
    return sorted(picked)


def generate_multiple_bets(
    stats: list[NumberStats],
    *,
    strategy: str,
    pick_count: int = 8,
    suggestion_count: int = 3,
    seed: int | None = None,
    min_balance: float = 0.45,
) -> list[MultipleBet]:
    pick_count = max(7, min(pick_count, 12))
    suggestion_count = max(1, min(suggestion_count, 10))
    rng = random.Random(seed)
    scores = _score_lookup(stats)
    bets: list[MultipleBet] = []
    seen: set[tuple[int, ...]] = set()

    top = _coverage_pool(stats, pick_count)
    top_key = tuple(top)
    seen.add(top_key)
    units = _multiple_units(pick_count)
    bets.append(
        MultipleBet(
            numbers=top_key,
            units=units,
            cost_hkd=units * UNIT_BET_HKD,
            ticket_score=_set_score(top, scores),
            balance=_estimate_set_balance(top),
            strategy=strategy,
        )
    )

    attempts = 0
    while len(bets) < suggestion_count and attempts < suggestion_count * 250:
        attempts += 1
        numbers = _diversified_pick(
            stats[:32],
            pick_count,
            rng,
            temperature=0.7 + 0.1 * len(bets),
            max_per_zone=3,
        )
        if len(numbers) != pick_count:
            continue
        balance = _estimate_set_balance(numbers)
        if balance < min_balance:
            continue
        key = tuple(numbers)
        if key in seen:
            continue
        seen.add(key)
        units = _multiple_units(pick_count)
        bets.append(
            MultipleBet(
                numbers=key,
                units=units,
                cost_hkd=units * UNIT_BET_HKD,
                ticket_score=_set_score(numbers, scores),
                balance=balance,
                strategy=strategy,
            )
        )

    bets.sort(key=lambda item: (item.ticket_score, item.balance), reverse=True)
    return bets[:suggestion_count]


def generate_banker_bets(
    stats: list[NumberStats],
    *,
    strategy: str,
    banker_count: int = 2,
    trailer_count: int = 8,
    suggestion_count: int = 3,
    seed: int | None = None,
    min_balance: float = 0.40,
) -> list[BankerBet]:
    banker_count = max(1, min(banker_count, 5))
    remaining = 6 - banker_count
    trailer_count = max(remaining, min(trailer_count, 20))
    suggestion_count = max(1, min(suggestion_count, 10))

    rng = random.Random(seed)
    scores = _score_lookup(stats)
    bets: list[BankerBet] = []
    seen: set[tuple[tuple[int, ...], tuple[int, ...]]] = set()

    # Bankers: mid-ranked stable numbers, not always #1/#2 hot
    ranked = [item.number for item in stats]
    banker_candidates = ranked[2 : 2 + max(8, banker_count * 4)]
    bankers = sorted(banker_candidates[:banker_count])
    trailer_pool = [n for n in ranked if n not in bankers]
    trailers = sorted(_coverage_pool(
        [item for item in stats if item.number in trailer_pool],
        trailer_count,
    ))
    if len(trailers) < trailer_count:
        trailers = sorted(trailer_pool[:trailer_count])

    key = (tuple(bankers), tuple(trailers))
    seen.add(key)
    units = _banker_units(banker_count, trailer_count)
    full = bankers + trailers
    bets.append(
        BankerBet(
            bankers=tuple(bankers),
            trailers=tuple(trailers),
            units=units,
            cost_hkd=units * UNIT_BET_HKD,
            ticket_score=_set_score(full, scores),
            balance=_estimate_set_balance(full),
            strategy=strategy,
        )
    )

    attempts = 0
    while len(bets) < suggestion_count and attempts < suggestion_count * 250:
        attempts += 1
        bankers = _diversified_pick(stats[1:22], banker_count, rng, temperature=0.7)
        if len(bankers) != banker_count:
            continue
        remaining_pool = [item for item in stats[:36] if item.number not in bankers]
        trailers = _diversified_pick(
            remaining_pool,
            trailer_count,
            rng,
            temperature=0.8,
            max_per_zone=3,
        )
        if len(trailers) != trailer_count:
            continue
        full = sorted(bankers + trailers)
        balance = _estimate_set_balance(full)
        if balance < min_balance:
            continue
        key = (tuple(bankers), tuple(trailers))
        if key in seen:
            continue
        seen.add(key)
        units = _banker_units(banker_count, trailer_count)
        bets.append(
            BankerBet(
                bankers=tuple(bankers),
                trailers=tuple(trailers),
                units=units,
                cost_hkd=units * UNIT_BET_HKD,
                ticket_score=_set_score(full, scores),
                balance=balance,
                strategy=strategy,
            )
        )

    bets.sort(key=lambda item: (item.ticket_score, item.balance), reverse=True)
    return bets[:suggestion_count]
