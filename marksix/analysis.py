"""Statistical scoring for Mark Six numbers."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from math import exp
from statistics import mean

from marksix.data import Draw

ALL_NUMBERS = tuple(range(1, 50))
ZONES = ((1, 10), (11, 20), (21, 30), (31, 40), (41, 49))


@dataclass(frozen=True)
class NumberStats:
    number: int
    frequency: int
    weighted_frequency: float
    gap: int
    avg_gap: float
    pair_strength: float
    composite_score: float


def _decay_weight(index: int, half_life: float = 40.0) -> float:
    return exp(-index / half_life)


def _frequency_scores(draws: list[Draw]) -> dict[int, float]:
    scores = {number: 0.0 for number in ALL_NUMBERS}
    for index, draw in enumerate(draws):
        weight = _decay_weight(index)
        for number in draw.numbers:
            scores[number] += weight
    maximum = max(scores.values()) or 1.0
    return {number: value / maximum for number, value in scores.items()}


def _gap_scores(draws: list[Draw]) -> dict[int, float]:
    last_seen: dict[int, int | None] = {number: None for number in ALL_NUMBERS}
    gaps: dict[int, list[int]] = {number: [] for number in ALL_NUMBERS}

    for index, draw in enumerate(reversed(draws)):
        for number in ALL_NUMBERS:
            if number in draw.numbers:
                if last_seen[number] is not None:
                    gaps[number].append(index - last_seen[number])
                last_seen[number] = index

    scores: dict[int, float] = {}
    for number in ALL_NUMBERS:
        current_gap = last_seen[number]
        if current_gap is None:
            scores[number] = 1.0
            continue
        current_gap = len(draws) - 1 - current_gap
        average_gap = mean(gaps[number]) if gaps[number] else max(len(draws), 1)
        ratio = current_gap / max(average_gap, 1.0)
        scores[number] = min(ratio / 2.0, 1.0)
    return scores


def _pair_scores(draws: list[Draw], top_numbers: set[int]) -> dict[int, float]:
    pair_counts: Counter[tuple[int, int]] = Counter()
    for draw in draws:
        for left, right in combinations(sorted(draw.numbers), 2):
            pair_counts[(left, right)] += 1

    scores = {number: 0.0 for number in ALL_NUMBERS}
    for number in top_numbers:
        related = 0.0
        for partner in top_numbers:
            if partner == number:
                continue
            key = tuple(sorted((number, partner)))
            related += pair_counts[key]
        scores[number] = related

    maximum = max(scores.values()) or 1.0
    return {number: value / maximum for number, value in scores.items()}


def _cold_scores(draws: list[Draw]) -> dict[int, float]:
    recent = draws[: min(30, len(draws))]
    counts = Counter(number for draw in recent for number in draw.numbers)
    minimum = min(counts.get(number, 0) for number in ALL_NUMBERS)
    maximum = max(counts.get(number, 0) for number in ALL_NUMBERS) or 1
    spread = maximum - minimum or 1
    return {
        number: (maximum - counts.get(number, 0)) / spread for number in ALL_NUMBERS
    }


def analyze_numbers(
    draws: list[Draw],
    *,
    strategy: str = "ensemble",
) -> list[NumberStats]:
    if not draws:
        raise ValueError("No draw history available for analysis.")

    frequency = _frequency_scores(draws)
    gap = _gap_scores(draws)
    cold = _cold_scores(draws)

    raw_counts = Counter(number for draw in draws for number in draw.numbers)
    weighted_counts = defaultdict(float)
    for index, draw in enumerate(draws):
        weight = _decay_weight(index)
        for number in draw.numbers:
            weighted_counts[number] += weight

    last_seen_index = {number: None for number in ALL_NUMBERS}
    gap_history: dict[int, list[int]] = {number: [] for number in ALL_NUMBERS}
    for index, draw in enumerate(reversed(draws)):
        for number in ALL_NUMBERS:
            if number in draw.numbers:
                if last_seen_index[number] is not None:
                    gap_history[number].append(index - last_seen_index[number])
                last_seen_index[number] = index

    gaps = {
        number: (
            len(draws) - 1 - last_seen_index[number]
            if last_seen_index[number] is not None
            else len(draws)
        )
        for number in ALL_NUMBERS
    }

    preliminary = sorted(
        ALL_NUMBERS,
        key=lambda number: frequency[number] * 0.6 + gap[number] * 0.4,
        reverse=True,
    )
    pair = _pair_scores(draws, set(preliminary[:18]))

    weights = {
        "hot": {"frequency": 0.75, "gap": 0.10, "pair": 0.10, "cold": 0.05},
        "cold": {"frequency": 0.10, "gap": 0.35, "pair": 0.10, "cold": 0.45},
        "overdue": {"frequency": 0.15, "gap": 0.65, "pair": 0.10, "cold": 0.10},
        "balanced": {"frequency": 0.40, "gap": 0.25, "pair": 0.25, "cold": 0.10},
        "ensemble": {"frequency": 0.45, "gap": 0.30, "pair": 0.15, "cold": 0.10},
    }[strategy]

    stats: list[NumberStats] = []
    for number in ALL_NUMBERS:
        composite = (
            frequency[number] * weights["frequency"]
            + gap[number] * weights["gap"]
            + pair[number] * weights["pair"]
            + cold[number] * weights["cold"]
        )
        stats.append(
            NumberStats(
                number=number,
                frequency=raw_counts[number],
                weighted_frequency=weighted_counts[number],
                gap=gaps[number],
                avg_gap=mean(gap_history[number]) if gap_history[number] else float(len(draws)),
                pair_strength=pair[number],
                composite_score=composite,
            )
        )

    stats.sort(key=lambda item: item.composite_score, reverse=True)
    return stats


def balance_score(numbers: list[int]) -> float:
    odd = sum(1 for number in numbers if number % 2 == 1)
    low = sum(1 for number in numbers if number <= 24)
    total = sum(numbers)
    zone_counts = [
        sum(1 for number in numbers if low_bound <= number <= high_bound)
        for low_bound, high_bound in ZONES
    ]

    odd_score = 1.0 - abs(odd - 3) / 3.0
    low_score = 1.0 - abs(low - 3) / 3.0
    sum_score = 1.0 - min(abs(total - 140) / 80.0, 1.0)
    empty_zones = sum(1 for count in zone_counts if count == 0)
    zone_score = 1.0 - empty_zones / 5.0
    spread = max(numbers) - min(numbers)
    spread_score = 1.0 if spread >= 20 else spread / 20.0

    return (
        odd_score * 0.25
        + low_score * 0.25
        + sum_score * 0.20
        + zone_score * 0.20
        + spread_score * 0.10
    )
