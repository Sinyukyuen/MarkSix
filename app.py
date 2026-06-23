"""Mark Six web application."""

from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from marksix.service import STRATEGIES, generate_predictions

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html", strategies=STRATEGIES)


@app.post("/api/generate")
def api_generate():
    payload = request.get_json(silent=True) or {}

    try:
        draws = int(payload.get("draws", 300))
        tickets = int(payload.get("tickets", 5))
        strategy = str(payload.get("strategy", "ensemble"))
        refresh = bool(payload.get("refresh", False))
        seed_value = payload.get("seed")
        seed = int(seed_value) if seed_value not in (None, "") else None

        result = generate_predictions(
            lookback_draws=draws,
            ticket_count=tickets,
            strategy=strategy,
            seed=seed,
            refresh=refresh,
        )
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Generation failed: {exc}"}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
