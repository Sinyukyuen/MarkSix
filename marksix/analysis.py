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
STRATEGIES = ("adaptive", "ensemble", "hot", "cold", "overdue", "balanced")


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


def _normalize(scores: dict[int, float]) -> dict[int, float]:
    maximum = max(scores.values()) if scores else 1.0
    if maximum <= 0:
        return {number: 0.0 for number in ALL_NUMBERS}
    return {number: value / maximum for number, value in scores.items()}


def _frequency_scores(draws: list[Draw], half_life: float = 40.0) -> dict[int, float]:
    scores = {number: 0.0 for number in ALL_NUMBERS}
    for index, draw in enumerate(draws):
        weight = _decay_weight(index, half_life=half_life)
        for number in draw.numbers:
            scores[number] += weight
    return _normalize(scores)


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
        # Prefer mildly overdue numbers; extreme gaps are noisy
        if ratio < 0.5:
            scores[number] = ratio
        elif ratio <= 1.8:
            scores[number] = 0.55 + 0.45 * min((ratio - 0.5) / 1.3, 1.0)
        else:
            scores[number] = max(0.2, 1.0 - (ratio - 1.8) / 3.0)
    return scores


def _pair_scores(draws: list[Draw], top_numbers: set[int]) -> dict[int, float]:
    pair_counts: Counter[tuple[int, int]] = Counter()
    for draw in draws[:120]:
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

    return _normalize(scores)


def _cold_scores(draws: list[Draw]) -> dict[int, float]:
    recent = draws[: min(30, len(draws))]
    counts = Counter(number for draw in recent for number in draw.numbers)
    minimum = min(counts.get(number, 0) for number in ALL_NUMBERS)
    maximum = max(counts.get(number, 0) for number in ALL_NUMBERS) or 1
    spread = maximum - minimum or 1
    return {
        number: (maximum - counts.get(number, 0)) / spread for number in ALL_NUMBERS
    }


def _mean_reversion_scores(draws: list[Draw]) -> dict[int, float]:
    """Prefer numbers under-represented in the short term vs longer baseline."""
    short = draws[:20]
    long = draws[: min(120, len(draws))]
    short_counts = Counter(n for draw in short for n in draw.numbers)
    long_counts = Counter(n for draw in long for n in draw.numbers)
    short_rate = {
        n: short_counts.get(n, 0) / max(len(short), 1) for n in ALL_NUMBERS
    }
    long_rate = {
        n: long_counts.get(n, 0) / max(len(long), 1) for n in ALL_NUMBERS
    }
    raw = {
        n: max(0.0, long_rate[n] - short_rate[n] + 0.15) for n in ALL_NUMBERS
    }
    return _normalize(raw)


def _skip_recent_scores(draws: list[Draw]) -> dict[int, float]:
    """Downweight numbers that just appeared (reduces sticky hot-number reuse)."""
    scores = {number: 1.0 for number in ALL_NUMBERS}
    for depth, draw in enumerate(draws[:3]):
        penalty = 0.85 if depth == 0 else 0.55 if depth == 1 else 0.3
        for number in draw.numbers:
            scores[number] = min(scores[number], 1.0 - penalty)
    return scores


def _mid_frequency_scores(draws: list[Draw]) -> dict[int, float]:
    """Prefer numbers near the historical average hit rate (avoid extremes)."""
    window = draws[: min(100, len(draws))]
    counts = Counter(n for draw in window for n in draw.numbers)
    expected = (6 * len(window)) / 49
    raw = {
        n: 1.0 / (1.0 + abs(counts.get(n, 0) - expected)) for n in ALL_NUMBERS
    }
    return _normalize(raw)


def analyze_numbers(
    draws: list[Draw],
    *,
    strategy: str = "ensemble",
) -> list[NumberStats]:
    if not draws:
        raise ValueError("No draw history available for analysis.")
    if strategy not in STRATEGIES:
        strategy = "ensemble"

    frequency = _frequency_scores(draws)
    frequency_fast = _frequency_scores(draws, half_life=18.0)
    gap = _gap_scores(draws)
    cold = _cold_scores(draws)
    reversion = _mean_reversion_scores(draws)
    skip_recent = _skip_recent_scores(draws)
    mid_freq = _mid_frequency_scores(draws)

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
        key=lambda number: (
            mid_freq[number] * 0.35
            + gap[number] * 0.30
            + reversion[number] * 0.20
            + frequency[number] * 0.15
        ),
        reverse=True,
    )
    pair = _pair_scores(draws, set(preliminary[:20]))

    weight_sets = {
        "hot": {
            "frequency": 0.55,
            "gap": 0.10,
            "pair": 0.15,
            "cold": 0.05,
            "reversion": 0.05,
            "skip": 0.05,
            "mid": 0.05,
        },
        "cold": {
            "frequency": 0.05,
            "gap": 0.25,
            "pair": 0.10,
            "cold": 0.35,
            "reversion": 0.15,
            "skip": 0.05,
            "mid": 0.05,
        },
        "overdue": {
            "frequency": 0.10,
            "gap": 0.45,
            "pair": 0.10,
            "cold": 0.10,
            "reversion": 0.10,
            "skip": 0.10,
            "mid": 0.05,
        },
        "balanced": {
            "frequency": 0.20,
            "gap": 0.20,
            "pair": 0.20,
            "cold": 0.10,
            "reversion": 0.10,
            "skip": 0.10,
            "mid": 0.10,
        },
        "ensemble": {
            "frequency": 0.25,
            "gap": 0.20,
            "pair": 0.15,
            "cold": 0.10,
            "reversion": 0.10,
            "skip": 0.10,
            "mid": 0.10,
        },
        # Default: fight hot-number stickiness; aim closer to random baseline
        "adaptive": {
            "frequency": 0.12,
            "gap": 0.18,
            "pair": 0.12,
            "cold": 0.08,
            "reversion": 0.22,
            "skip": 0.16,
            "mid": 0.12,
        },
    }
    weights = weight_sets[strategy]

    stats: list[NumberStats] = []
    for number in ALL_NUMBERS:
        # Blend slow + fast frequency so neither dominates
        freq_blend = frequency[number] * 0.65 + frequency_fast[number] * 0.35
        composite = (
            freq_blend * weights["frequency"]
            + gap[number] * weights["gap"]
            + pair[number] * weights["pair"]
            + cold[number] * weights["cold"]
            + reversion[number] * weights["reversion"]
            + skip_recent[number] * weights["skip"]
            + mid_freq[number] * weights["mid"]
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
    # Penalize crowding in one decade
    crowded = max(zone_counts) if zone_counts else 0
    crowd_score = 1.0 - max(0, crowded - 2) / 4.0

    return (
        odd_score * 0.20
        + low_score * 0.20
        + sum_score * 0.15
        + zone_score * 0.20
        + spread_score * 0.10
        + crowd_score * 0.15
    )


def zone_of(number: int) -> int:
    for index, (low, high) in enumerate(ZONES):
        if low <= number <= high:
            return index
    return 4
