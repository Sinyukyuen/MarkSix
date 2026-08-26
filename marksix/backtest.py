"""Backtest predictions against historical Mark Six draws (復盤)."""

from __future__ import annotations

from collections import Counter

from marksix.analysis import STRATEGIES, analyze_numbers
from marksix.data import Draw, get_draw_history
from marksix.generator import (
    BET_TYPES,
    generate_banker_bets,
    generate_multiple_bets,
    generate_tickets,
)
from marksix.prizes import prize_info, prize_tier
from marksix.service import BET_TYPE_LABELS, _serialize_draw, ball_color


def _score_single(
    predicted: set[int],
    special: int | None,
    actual: set[int],
    actual_special: int,
) -> dict:
    hits = sorted(predicted & actual)
    special_hit = special is not None and special == actual_special
    main_hits = len(hits)
    tier = prize_tier(main_hits, special_hit)
    info = prize_info(tier)
    return {
        "main_hits": main_hits,
        "hit_numbers": hits,
        "miss_numbers": sorted(predicted - actual),
        "special_hit": special_hit,
        "prize_tier": tier,
        "prize": info,
    }


def _score_pool(pool: set[int], actual: set[int], actual_special: int) -> dict:
    hits = sorted(pool & actual)
    special_hit = actual_special in pool
    main_hits = len(hits)
    tier = prize_tier(main_hits, special_hit)
    info = prize_info(tier)
    return {
        "main_hits": main_hits,
        "hit_numbers": hits,
        "miss_numbers": sorted(actual - pool),
        "special_hit": special_hit,
        "prize_tier": tier,
        "prize": info,
        "covered": main_hits,
        "pool_size": len(pool),
    }


def _predict_for_history(
    history: list[Draw],
    *,
    strategy: str,
    bet_type: str,
    pick_count: int,
    banker_count: int,
    trailer_count: int,
    seed: int,
    candidates: int = 5,
) -> dict:
    stats = analyze_numbers(history, strategy=strategy)

    if bet_type == "multiple":
        bets = generate_multiple_bets(
            stats,
            strategy=strategy,
            pick_count=pick_count,
            suggestion_count=max(1, candidates),
            seed=seed,
        )
        primary = bets[0]
        return {
            "type": "multiple",
            "numbers": list(primary.numbers),
            "pool": list(primary.numbers),
            "units": primary.units,
            "cost_hkd": primary.cost_hkd,
            "candidates": [
                {"numbers": list(bet.numbers), "pool": list(bet.numbers)} for bet in bets
            ],
        }

    if bet_type == "banker":
        bets = generate_banker_bets(
            stats,
            strategy=strategy,
            banker_count=banker_count,
            trailer_count=trailer_count,
            suggestion_count=max(1, candidates),
            seed=seed,
        )
        primary = bets[0]
        pool = list(primary.bankers) + list(primary.trailers)
        return {
            "type": "banker",
            "bankers": list(primary.bankers),
            "trailers": list(primary.trailers),
            "pool": pool,
            "units": primary.units,
            "cost_hkd": primary.cost_hkd,
            "candidates": [
                {
                    "bankers": list(bet.bankers),
                    "trailers": list(bet.trailers),
                    "pool": list(bet.bankers) + list(bet.trailers),
                }
                for bet in bets
            ],
        }

    tickets = generate_tickets(
        stats,
        strategy=strategy,
        count=max(1, candidates),
        seed=seed,
    )
    primary = tickets[0]
    return {
        "type": "single",
        "numbers": list(primary.numbers),
        "special": primary.special,
        "pool": list(primary.numbers),
        "units": 1,
        "cost_hkd": 10 * len(tickets),
        "candidates": [
            {
                "numbers": list(ticket.numbers),
                "special": ticket.special,
                "pool": list(ticket.numbers),
            }
            for ticket in tickets
        ],
    }


def _best_candidate_comparison(
    prediction: dict,
    bet_type: str,
    actual_set: set[int],
    actual_special: int,
) -> dict:
    best = None
    for candidate in prediction.get("candidates", [prediction]):
        if bet_type == "single":
            comparison = _score_single(
                set(candidate["numbers"]),
                candidate.get("special"),
                actual_set,
                actual_special,
            )
        else:
            comparison = _score_pool(
                set(candidate["pool"]),
                actual_set,
                actual_special,
            )
        if best is None or comparison["main_hits"] > best["main_hits"]:
            best = comparison
        elif (
            best is not None
            and comparison["main_hits"] == best["main_hits"]
            and comparison["special_hit"]
            and not best["special_hit"]
        ):
            best = comparison
    return best or {
        "main_hits": 0,
        "hit_numbers": [],
        "miss_numbers": [],
        "special_hit": False,
        "prize_tier": None,
        "prize": None,
    }


def run_backtest(
    *,
    review_draws: int = 20,
    lookback_draws: int = 300,
    strategy: str = "ensemble",
    bet_type: str = "single",
    pick_count: int = 8,
    banker_count: int = 2,
    trailer_count: int = 8,
    seed: int | None = 42,
    refresh: bool = False,
    use_cache: bool = True,
    candidates: int = 5,
    all_history: bool = False,
) -> dict:
    """
    For each of the last `review_draws` results, predict using only older history
    and compare against the actual draw.
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy}")
    if bet_type not in BET_TYPES:
        raise ValueError(f"Unknown bet type: {bet_type}")

    review_draws = max(5, min(review_draws, 50))
    if not all_history:
        lookback_draws = max(30, min(lookback_draws, 1000))
    pick_count = max(7, min(pick_count, 12))
    banker_count = max(1, min(banker_count, 5))
    trailer_count = max(6 - banker_count, min(trailer_count, 20))
    candidates = max(1, min(candidates, 10))
    base_seed = 42 if seed is None else seed

    if all_history:
        draws = get_draw_history(
            refresh=refresh,
            use_cache=use_cache,
            all_history=True,
        )
    else:
        total_needed = review_draws + lookback_draws
        draws = get_draw_history(
            lookback_draws=total_needed,
            refresh=refresh,
            use_cache=use_cache,
        )
    if len(draws) < review_draws + 30:
        raise RuntimeError("Not enough draw history for backtest.")

    if all_history:
        lookback_draws = max(30, len(draws) - review_draws)

    max_reviews = min(review_draws, len(draws) - 30)
    rows: list[dict] = []
    hit_counter: Counter[int] = Counter()
    best_hit_counter: Counter[int] = Counter()
    prize_counter: Counter[int] = Counter()
    best_prize_counter: Counter[int] = Counter()
    total_main_hits = 0
    total_best_hits = 0
    special_hits = 0
    total_cost = 0

    for index in range(max_reviews):
        actual = draws[index]
        history = draws[index + 1 : index + 1 + lookback_draws]
        if len(history) < 30:
            break

        prediction = _predict_for_history(
            history,
            strategy=strategy,
            bet_type=bet_type,
            pick_count=pick_count,
            banker_count=banker_count,
            trailer_count=trailer_count,
            seed=base_seed + index,
            candidates=candidates,
        )

        actual_set = set(actual.numbers)
        if bet_type == "single":
            comparison = _score_single(
                set(prediction["numbers"]),
                prediction.get("special"),
                actual_set,
                actual.special,
            )
        else:
            comparison = _score_pool(
                set(prediction["pool"]),
                actual_set,
                actual.special,
            )

        best_comparison = _best_candidate_comparison(
            prediction, bet_type, actual_set, actual.special
        )

        hit_counter[comparison["main_hits"]] += 1
        best_hit_counter[best_comparison["main_hits"]] += 1
        total_main_hits += comparison["main_hits"]
        total_best_hits += best_comparison["main_hits"]
        if comparison["special_hit"]:
            special_hits += 1
        if comparison["prize_tier"]:
            prize_counter[comparison["prize_tier"]] += 1
        if best_comparison["prize_tier"]:
            best_prize_counter[best_comparison["prize_tier"]] += 1
        total_cost += prediction["cost_hkd"]

        if bet_type == "banker":
            predicted_view = {
                "type": "banker",
                "bankers": prediction["bankers"],
                "trailers": prediction["trailers"],
            }
        else:
            predicted_view = {
                "type": bet_type,
                "numbers": prediction["numbers"],
            }
            if bet_type == "single":
                predicted_view["special"] = prediction["special"]

        scored_candidates: list[dict] = []
        for rank, candidate in enumerate(prediction.get("candidates", []), start=1):
            if bet_type == "single":
                cand_comparison = _score_single(
                    set(candidate["numbers"]),
                    candidate.get("special"),
                    actual_set,
                    actual.special,
                )
                cand_view = {
                    "type": "single",
                    "numbers": candidate["numbers"],
                    "special": candidate.get("special"),
                }
            elif bet_type == "banker":
                cand_comparison = _score_pool(
                    set(candidate["pool"]),
                    actual_set,
                    actual.special,
                )
                cand_view = {
                    "type": "banker",
                    "bankers": candidate["bankers"],
                    "trailers": candidate["trailers"],
                }
            else:
                cand_comparison = _score_pool(
                    set(candidate["pool"]),
                    actual_set,
                    actual.special,
                )
                cand_view = {
                    "type": "multiple",
                    "numbers": candidate["numbers"],
                }
            scored_candidates.append(
                {
                    "rank": rank,
                    "predicted": cand_view,
                    "comparison": cand_comparison,
                }
            )

        rows.append(
            {
                "draw": _serialize_draw(actual),
                "predicted": predicted_view,
                "comparison": comparison,
                "best_comparison": best_comparison,
                "candidates": scored_candidates,
                "candidate_count": len(scored_candidates),
                "units": prediction["units"],
                "cost_hkd": prediction["cost_hkd"],
            }
        )

    reviewed = len(rows)
    avg_hits = round(total_main_hits / reviewed, 2) if reviewed else 0.0
    avg_best = round(total_best_hits / reviewed, 2) if reviewed else 0.0

    random_expected = round(6 * (6 / 49), 2)
    if bet_type == "multiple":
        random_expected = round(pick_count * (6 / 49), 2)
    elif bet_type == "banker":
        pool_size = banker_count + trailer_count
        random_expected = round(pool_size * (6 / 49), 2)

    return {
        "strategy": strategy,
        "bet_type": bet_type,
        "bet_type_label": BET_TYPE_LABELS[bet_type],
        "lookback_draws": lookback_draws,
        "all_history": all_history,
        "review_draws": reviewed,
        "candidates": candidates,
        "seed": base_seed,
        "summary": {
            "avg_main_hits": avg_hits,
            "avg_best_hits": avg_best,
            "random_expected_hits": random_expected,
            "vs_random": round(avg_hits - random_expected, 2),
            "best_vs_random": round(avg_best - random_expected, 2),
            "special_hit_rate": round(special_hits / reviewed, 3) if reviewed else 0,
            "hit_distribution": {str(k): hit_counter[k] for k in range(0, 7)},
            "best_hit_distribution": {str(k): best_hit_counter[k] for k in range(0, 7)},
            "prize_counts": {str(k): prize_counter[k] for k in sorted(prize_counter)},
            "best_prize_total": sum(best_prize_counter.values()),
            "prize_total": sum(prize_counter.values()),
            "total_cost_hkd": total_cost,
        },
        "rows": rows,
        "colors": {str(n): ball_color(n) for n in range(1, 50)},
    }
