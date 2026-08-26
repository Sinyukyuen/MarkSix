"""Shared generation logic for CLI and web."""

from __future__ import annotations

from dataclasses import asdict

from marksix.analysis import STRATEGIES, analyze_numbers
from marksix.data import Draw, get_draw_history
from marksix.generator import (
    BET_TYPES,
    BankerBet,
    MultipleBet,
    Ticket,
    generate_banker_bets,
    generate_multiple_bets,
    generate_tickets,
)

DISCLAIMER = (
    "Mark Six is a random lottery. This tool uses historical draw patterns "
    "(frequency, gaps, pairs, balance) to suggest combinations - it cannot "
    "guarantee a win or improve true odds beyond random selection."
)

BET_TYPE_LABELS = {
    "single": "單式",
    "multiple": "復式",
    "banker": "拖膽",
}


def ball_color(number: int) -> str:
    color_index = ((number - 1) + ((number - 1) // 10)) % 6 // 2
    if color_index == 0:
        return "red"
    if color_index == 1:
        return "blue"
    return "green"


def _serialize_draw(draw: Draw) -> dict:
    return {
        "draw_id": draw.draw_id,
        "draw_date": draw.draw_date.date().isoformat(),
        "numbers": list(draw.numbers),
        "special": draw.special,
    }


def _serialize_ticket(ticket: Ticket) -> dict:
    return {
        "type": "single",
        "numbers": list(ticket.numbers),
        "special": ticket.special,
        "ticket_score": round(ticket.ticket_score, 2),
        "balance": round(ticket.balance, 2),
        "strategy": ticket.strategy,
        "units": 1,
        "cost_hkd": 10,
    }


def _serialize_multiple(bet: MultipleBet) -> dict:
    return {
        "type": "multiple",
        "numbers": list(bet.numbers),
        "ticket_score": round(bet.ticket_score, 2),
        "balance": round(bet.balance, 2),
        "strategy": bet.strategy,
        "units": bet.units,
        "cost_hkd": bet.cost_hkd,
    }


def _serialize_banker(bet: BankerBet) -> dict:
    return {
        "type": "banker",
        "bankers": list(bet.bankers),
        "trailers": list(bet.trailers),
        "ticket_score": round(bet.ticket_score, 2),
        "balance": round(bet.balance, 2),
        "strategy": bet.strategy,
        "units": bet.units,
        "cost_hkd": bet.cost_hkd,
    }


def _serialize_stats(stats, top_numbers_limit: int) -> list[dict]:
    return [
        {
            **asdict(item),
            "composite_score": round(item.composite_score, 3),
            "weighted_frequency": round(item.weighted_frequency, 2),
            "pair_strength": round(item.pair_strength, 2),
            "avg_gap": round(item.avg_gap, 1),
            "color": ball_color(item.number),
        }
        for item in stats[:top_numbers_limit]
    ]


def generate_predictions(
    *,
    lookback_draws: int = 300,
    ticket_count: int = 5,
    strategy: str = "ensemble",
    bet_type: str = "single",
    pick_count: int = 8,
    banker_count: int = 2,
    trailer_count: int = 8,
    seed: int | None = None,
    refresh: bool = False,
    use_cache: bool = True,
    top_numbers_limit: int = 15,
    all_history: bool = False,
) -> dict:
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy}")
    if bet_type not in BET_TYPES:
        raise ValueError(f"Unknown bet type: {bet_type}")

    if not all_history:
        lookback_draws = max(20, min(lookback_draws, 1000))
    ticket_count = max(1, min(ticket_count, 20))
    top_numbers_limit = max(5, min(top_numbers_limit, 49))
    pick_count = max(7, min(pick_count, 12))
    banker_count = max(1, min(banker_count, 5))
    trailer_count = max(6 - banker_count, min(trailer_count, 20))

    draws = get_draw_history(
        lookback_draws=lookback_draws,
        refresh=refresh,
        use_cache=use_cache,
        all_history=all_history,
    )
    if not draws:
        raise RuntimeError("No draw data available.")

    if all_history:
        lookback_draws = len(draws)
    stats = analyze_numbers(draws, strategy=strategy)

    if bet_type == "multiple":
        bets = generate_multiple_bets(
            stats,
            strategy=strategy,
            pick_count=pick_count,
            suggestion_count=ticket_count,
            seed=seed,
        )
        suggestions = [_serialize_multiple(bet) for bet in bets]
    elif bet_type == "banker":
        bets = generate_banker_bets(
            stats,
            strategy=strategy,
            banker_count=banker_count,
            trailer_count=trailer_count,
            suggestion_count=ticket_count,
            seed=seed,
        )
        suggestions = [_serialize_banker(bet) for bet in bets]
    else:
        tickets = generate_tickets(
            stats,
            strategy=strategy,
            count=ticket_count,
            seed=seed,
        )
        suggestions = [_serialize_ticket(ticket) for ticket in tickets]

    return {
        "disclaimer": DISCLAIMER,
        "draw_count": len(draws),
        "latest_draw": _serialize_draw(draws[0]),
        "strategy": strategy,
        "bet_type": bet_type,
        "bet_type_label": BET_TYPE_LABELS[bet_type],
        "options": {
            "pick_count": pick_count,
            "banker_count": banker_count,
            "trailer_count": trailer_count,
            "all_history": all_history,
            "lookback_draws": lookback_draws,
        },
        "top_numbers": _serialize_stats(stats, top_numbers_limit),
        "tickets": suggestions,
        "suggestions": suggestions,
    }
