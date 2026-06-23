#!/usr/bin/env python3
"""Generate statistically-informed Mark Six number combinations."""

from __future__ import annotations

import argparse
import sys
from textwrap import dedent

from marksix.analysis import analyze_numbers
from marksix.data import get_draw_history
from marksix.generator import generate_tickets

STRATEGIES = ("ensemble", "hot", "cold", "overdue", "balanced")

DISCLAIMER = dedent(
    """
    Mark Six is a random lottery. This tool uses historical draw patterns
    (frequency, gaps, pairs, balance) to suggest combinations - it cannot
    guarantee a win or improve true odds beyond random selection.
    """
).strip()


def _format_numbers(numbers: tuple[int, ...]) -> str:
    return ", ".join(f"{number:02d}" for number in numbers)


def _print_top_numbers(stats, limit: int = 15) -> None:
    print("\nTop numbers by composite score:")
    print(f"{'No.':>4}  {'Freq':>5}  {'Gap':>4}  {'Pair':>5}  {'Score':>6}")
    print("-" * 34)
    for item in stats[:limit]:
        print(
            f"{item.number:4d}  {item.frequency:5d}  {item.gap:4d}  "
            f"{item.pair_strength:5.2f}  {item.composite_score:6.3f}"
        )


def _print_tickets(tickets) -> None:
    print("\nSuggested tickets:")
    for index, ticket in enumerate(tickets, start=1):
        print(
            f"  {index}. [{_format_numbers(ticket.numbers)}]  "
            f"+ special {ticket.special:02d}  "
            f"(score {ticket.ticket_score:.2f}, balance {ticket.balance:.2f})"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate Mark Six number suggestions from HKJC historical draws.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=DISCLAIMER,
    )
    parser.add_argument(
        "--draws",
        type=int,
        default=300,
        help="Number of recent draws to analyze (default: 300)",
    )
    parser.add_argument(
        "--tickets",
        type=int,
        default=5,
        help="How many ticket suggestions to output (default: 5)",
    )
    parser.add_argument(
        "--strategy",
        choices=STRATEGIES,
        default="ensemble",
        help="Scoring strategy (default: ensemble)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible ticket generation",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force refresh draw history from HKJC",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Do not read or write local draw cache",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    print("Mark Six Number Generator")
    print("=" * 28)
    print(DISCLAIMER)
    print()

    try:
        draws = get_draw_history(
            lookback_draws=args.draws,
            refresh=args.refresh,
            use_cache=not args.no_cache,
        )
    except Exception as exc:
        print(f"Failed to fetch draw history: {exc}", file=sys.stderr)
        return 1

    if not draws:
        print("No draw data available.", file=sys.stderr)
        return 1

    latest = draws[0]
    print(
        f"Loaded {len(draws)} draws. Latest: {latest.draw_id} "
        f"({latest.draw_date.date()}) -> {_format_numbers(latest.numbers)} + {latest.special:02d}"
    )

    stats = analyze_numbers(draws, strategy=args.strategy)
    tickets = generate_tickets(
        stats,
        strategy=args.strategy,
        count=args.tickets,
        seed=args.seed,
    )

    print(f"\nStrategy: {args.strategy}")
    _print_top_numbers(stats)
    _print_tickets(tickets)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
