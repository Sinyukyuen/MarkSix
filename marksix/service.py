"""Shared generation logic for CLI and web."""

from __future__ import annotations

from dataclasses import asdict

from marksix.analysis import analyze_numbers
from marksix.data import Draw, get_draw_history
from marksix.generator import Ticket, generate_tickets

STRATEGIES = ("ensemble", "hot", "cold", "overdue", "balanced")

DISCLAIMER = (
    "Mark Six is a random lottery. This tool uses historical draw patterns "
    "(frequency, gaps, pairs, balance) to suggest combinations - it cannot "
    "guarantee a win or improve true odds beyond random selection."
)


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
        "numbers": list(ticket.numbers),
        "special": ticket.special,
        "ticket_score": round(ticket.ticket_score, 2),
        "balance": round(ticket.balance, 2),
        "strategy": ticket.strategy,
    }


def generate_predictions(
    *,
    lookback_draws: int = 300,
    ticket_count: int = 5,
    strategy: str = "ensemble",
    seed: int | None = None,
    refresh: bool = False,
    use_cache: bool = True,
    top_numbers_limit: int = 15,
) -> dict:
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy}")

    lookback_draws = max(20, min(lookback_draws, 1000))
    ticket_count = max(1, min(ticket_count, 20))
    top_numbers_limit = max(5, min(top_numbers_limit, 49))

    draws = get_draw_history(
        lookback_draws=lookback_draws,
        refresh=refresh,
        use_cache=use_cache,
    )
    if not draws:
        raise RuntimeError("No draw data available.")

    stats = analyze_numbers(draws, strategy=strategy)
    tickets = generate_tickets(
        stats,
        strategy=strategy,
        count=ticket_count,
        seed=seed,
    )

    return {
        "disclaimer": DISCLAIMER,
        "draw_count": len(draws),
        "latest_draw": _serialize_draw(draws[0]),
        "strategy": strategy,
        "top_numbers": [
            {
                **asdict(item),
                "composite_score": round(item.composite_score, 3),
                "weighted_frequency": round(item.weighted_frequency, 2),
                "pair_strength": round(item.pair_strength, 2),
                "avg_gap": round(item.avg_gap, 1),
                "color": ball_color(item.number),
            }
            for item in stats[:top_numbers_limit]
        ],
        "tickets": [_serialize_ticket(ticket) for ticket in tickets],
    }
