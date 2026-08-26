"""Sweep lookback draw counts to find best 分析期數 settings."""

from __future__ import annotations

import json
from pathlib import Path

from marksix.backtest import run_backtest

LOOKBACKS = [50, 100, 150, 200, 300, 400, 500, 750, 1000]
STRATEGIES = ["adaptive", "ensemble", "balanced", "overdue", "cold", "hot"]
REVIEW = 30
BET_TYPE = "single"
OUT = Path(__file__).resolve().parent / "data" / "lookback_sweep.json"


def main() -> None:
    print(f"Backtest sweep: review={REVIEW}, bet={BET_TYPE}, candidates=5")
    print(
        f"{'lookback':>8} {'strategy':>10} {'avg':>6} {'best':>6} "
        f"{'vs_rnd':>7} {'best_vs':>7} {'prize':>5} {'best_p':>6}"
    )
    print("-" * 72)

    rows: list[dict] = []
    for strategy in STRATEGIES:
        for lookback in LOOKBACKS:
            try:
                result = run_backtest(
                    review_draws=REVIEW,
                    lookback_draws=lookback,
                    strategy=strategy,
                    bet_type=BET_TYPE,
                    seed=42,
                    refresh=False,
                    use_cache=True,
                    candidates=5,
                    all_history=False,
                )
                summary = result["summary"]
                row = {
                    "lookback": lookback,
                    "strategy": strategy,
                    "avg_main_hits": summary["avg_main_hits"],
                    "avg_best_hits": summary["avg_best_hits"],
                    "vs_random": summary["vs_random"],
                    "best_vs_random": summary["best_vs_random"],
                    "prize_total": summary["prize_total"],
                    "best_prize_total": summary["best_prize_total"],
                    "random_expected_hits": summary["random_expected_hits"],
                    "review_draws": result["review_draws"],
                }
                rows.append(row)
                print(
                    f"{lookback:8d} {strategy:>10} "
                    f"{summary['avg_main_hits']:6.2f} {summary['avg_best_hits']:6.2f} "
                    f"{summary['vs_random']:7.2f} {summary['best_vs_random']:7.2f} "
                    f"{summary['prize_total']:5d} {summary['best_prize_total']:6d}"
                )
            except Exception as exc:  # noqa: BLE001
                print(f"{lookback:8d} {strategy:>10} ERROR: {exc}")

    if not rows:
        print("No results.")
        return

    best_avg = max(rows, key=lambda item: (item["avg_main_hits"], item["vs_random"]))
    best_of = max(rows, key=lambda item: (item["avg_best_hits"], item["best_vs_random"]))
    best_prize = max(
        rows, key=lambda item: (item["best_prize_total"], item["avg_best_hits"])
    )

    # Average across strategies for each lookback
    by_lookback: dict[int, list[dict]] = {}
    for row in rows:
        by_lookback.setdefault(row["lookback"], []).append(row)

    lookback_rank = []
    for lookback, group in by_lookback.items():
        avg_hits = sum(item["avg_main_hits"] for item in group) / len(group)
        avg_best = sum(item["avg_best_hits"] for item in group) / len(group)
        avg_prize = sum(item["best_prize_total"] for item in group) / len(group)
        lookback_rank.append(
            {
                "lookback": lookback,
                "mean_avg_hits": round(avg_hits, 3),
                "mean_best_hits": round(avg_best, 3),
                "mean_best_prize": round(avg_prize, 2),
            }
        )
    lookback_rank.sort(key=lambda item: item["mean_best_hits"], reverse=True)

    print()
    print("Average across strategies by lookback (sorted by best-of-5 hits):")
    for item in lookback_rank:
        print(
            f"  lookback={item['lookback']:>4}: "
            f"avg={item['mean_avg_hits']:.3f}, "
            f"best5={item['mean_best_hits']:.3f}, "
            f"prize={item['mean_best_prize']:.1f}"
        )

    print()
    print("BEST primary avg hits:", best_avg)
    print("BEST best-of-5 avg hits:", best_of)
    print("BEST prize (best-of-5):", best_prize)
    print("RECOMMENDED lookback (by mean best-of-5):", lookback_rank[0]["lookback"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "rows": rows,
                "lookback_rank": lookback_rank,
                "best_avg": best_avg,
                "best_of": best_of,
                "best_prize": best_prize,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
