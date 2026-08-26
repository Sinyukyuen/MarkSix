"""Mark Six web application."""

from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from marksix.backtest import run_backtest
from marksix.generator import BET_TYPES
from marksix.prizes import public_prize_table
from marksix.service import BET_TYPE_LABELS, STRATEGIES, generate_predictions

app = Flask(__name__)


def _page_context(page: str) -> dict:
    return {
        "page": page,
        "strategies": STRATEGIES,
        "bet_types": BET_TYPES,
        "bet_type_labels": BET_TYPE_LABELS,
        "prize_table": public_prize_table(),
    }


@app.get("/")
def index():
    return render_template("index.html", **_page_context("predict"))


@app.get("/backtest")
def backtest_page():
    return render_template("backtest.html", **_page_context("backtest"))


@app.post("/api/generate")
def api_generate():
    payload = request.get_json(silent=True) or {}

    try:
        draws = int(payload.get("draws", 300))
        tickets = int(payload.get("tickets", 5))
        strategy = str(payload.get("strategy", "ensemble"))
        bet_type = str(payload.get("bet_type", "single"))
        pick_count = int(payload.get("pick_count", 8))
        banker_count = int(payload.get("banker_count", 2))
        trailer_count = int(payload.get("trailer_count", 8))
        all_history = bool(payload.get("all_history", False)) or draws >= 1050
        seed_value = payload.get("seed")
        seed = int(seed_value) if seed_value not in (None, "") else None

        result = generate_predictions(
            lookback_draws=draws,
            ticket_count=tickets,
            strategy=strategy,
            bet_type=bet_type,
            pick_count=pick_count,
            banker_count=banker_count,
            trailer_count=trailer_count,
            seed=seed,
            refresh=True,
            all_history=all_history,
        )
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Generation failed: {exc}"}), 500


@app.post("/api/backtest")
def api_backtest():
    payload = request.get_json(silent=True) or {}

    try:
        lookback = int(payload.get("draws", 300))
        review = int(payload.get("review_draws", 20))
        strategy = str(payload.get("strategy", "ensemble"))
        bet_type = str(payload.get("bet_type", "single"))
        pick_count = int(payload.get("pick_count", 8))
        banker_count = int(payload.get("banker_count", 2))
        trailer_count = int(payload.get("trailer_count", 8))
        all_history = bool(payload.get("all_history", False)) or lookback >= 1050
        seed_value = payload.get("seed")
        seed = int(seed_value) if seed_value not in (None, "") else 42
        show_predictions = int(payload.get("show_predictions", payload.get("candidates", 5)))
        candidates = max(show_predictions, 10)

        result = run_backtest(
            review_draws=review,
            lookback_draws=lookback,
            strategy=strategy,
            bet_type=bet_type,
            pick_count=pick_count,
            banker_count=banker_count,
            trailer_count=trailer_count,
            seed=seed,
            refresh=True,
            candidates=candidates,
            all_history=all_history,
        )
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Backtest failed: {exc}"}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
