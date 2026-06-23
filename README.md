# MarkSix

Python tool to generate Mark Six (六合彩) number suggestions using Hong Kong Jockey Club historical draw data.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
python generate_marksix.py
python generate_marksix.py --draws 500 --tickets 10 --strategy hot
python generate_marksix.py --strategy overdue --seed 42
```

### Options

| Flag | Description |
|------|-------------|
| `--draws` | Number of recent draws to analyze (default: 300) |
| `--tickets` | How many ticket suggestions to output (default: 5) |
| `--strategy` | `ensemble`, `hot`, `cold`, `overdue`, or `balanced` |
| `--seed` | Random seed for reproducible output |
| `--refresh` | Force refresh from HKJC API |
| `--no-cache` | Skip local cache in `data/draws_cache.json` |

## How it works

1. Fetches recent Mark Six results from the HKJC GraphQL API
2. Scores each number (1–49) using:
   - **Frequency** — weighted recent appearance rate
   - **Gap** — how overdue a number is vs its historical average gap
   - **Pairs** — numbers that often appear together
   - **Balance** — odd/even, low/high, zone spread patterns seen in real draws
3. Generates ticket combinations that score highly while matching typical draw balance

## Disclaimer

Mark Six is a game of chance. Each draw is independent and every combination has the same true probability. This script identifies patterns in past data for entertainment and analysis — it does **not** guarantee wins or beat the odds.
