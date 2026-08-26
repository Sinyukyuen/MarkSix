#!/usr/bin/env python3
"""Generate statistically-informed Mark Six number combinations."""

from __future__ import annotations

import argparse
import sys

from marksix.generator import BET_TYPES
from marksix.service import BET_TYPE_LABELS, DISCLAIMER, STRATEGIES, generate_predictions


def _format_numbers(numbers) -> str:
    return ", ".join(f"{int(number):02d}" for number in numbers)


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
        help="How many suggestions to output (default: 5)",
    )
    parser.add_argument(
        "--strategy",
        choices=STRATEGIES,
        default="ensemble",
        help="Scoring strategy (default: ensemble)",
    )
    parser.add_argument(
        "--bet-type",
        choices=BET_TYPES,
        default="single",
        help="Bet type: single (單式), multiple (復式), banker (拖膽)",
    )
    parser.add_argument(
        "--pick-count",
        type=int,
        default=8,
        help="復式 number count (7-12, default: 8)",
    )
    parser.add_argument(
        "--banker-count",
        type=int,
        default=2,
        help="拖膽 banker count (1-5, default: 2)",
    )
    parser.add_argument(
        "--trailer-count",
        type=int,
        default=8,
        help="拖膽 trailer count (default: 8)",
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


def _print_suggestions(result: dict) -> None:
    label = result["bet_type_label"]
    print(f"\nSuggested {label}:")
    for index, ticket in enumerate(result["suggestions"], start=1):
        if ticket["type"] == "banker":
            bankers = _format_numbers(ticket["bankers"])
            trailers = _format_numbers(ticket["trailers"])
            print(
                f"  {index}. 膽 [{bankers}]  拖 [{trailers}]  "
                f"({ticket['units']} 注 / ${ticket['cost_hkd']}, "
                f"score {ticket['ticket_score']:.2f})"
            )
        elif ticket["type"] == "multiple":
            numbers = _format_numbers(ticket["numbers"])
            print(
                f"  {index}. [{numbers}]  "
                f"({ticket['units']} 注 / ${ticket['cost_hkd']}, "
                f"score {ticket['ticket_score']:.2f})"
            )
        else:
            numbers = _format_numbers(ticket["numbers"])
            print(
                f"  {index}. [{numbers}]  "
                f"+ special {ticket['special']:02d}  "
                f"(score {ticket['ticket_score']:.2f}, balance {ticket['balance']:.2f})"
            )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    print("Mark Six Number Generator")
    print("=" * 28)
    print(DISCLAIMER)
    print()

    try:
        result = generate_predictions(
            lookback_draws=args.draws,
            ticket_count=args.tickets,
            strategy=args.strategy,
            bet_type=args.bet_type,
            pick_count=args.pick_count,
            banker_count=args.banker_count,
            trailer_count=args.trailer_count,
            seed=args.seed,
            refresh=args.refresh,
            use_cache=not args.no_cache,
        )
    except Exception as exc:
        print(f"Failed to generate predictions: {exc}", file=sys.stderr)
        return 1

    latest = result["latest_draw"]
    print(
        f"Loaded {result['draw_count']} draws. Latest: {latest['draw_id']} "
        f"({latest['draw_date']}) -> {_format_numbers(latest['numbers'])} + {latest['special']:02d}"
    )

    print(f"\nStrategy: {args.strategy} | Bet type: {result['bet_type_label']}")
    print("\nTop numbers by composite score:")
    print(f"{'No.':>4}  {'Freq':>5}  {'Gap':>4}  {'Pair':>5}  {'Score':>6}")
    print("-" * 34)
    for item in result["top_numbers"]:
        print(
            f"{item['number']:4d}  {item['frequency']:5d}  {item['gap']:4d}  "
            f"{item['pair_strength']:5.2f}  {item['composite_score']:6.3f}"
        )

    _print_suggestions(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
