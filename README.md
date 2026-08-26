# MarkSix

Python tool and web app to generate Mark Six (六合彩) number suggestions — **單式**, **復式**, and **拖膽** — using Hong Kong Jockey Club historical draw data.

## Setup

```bash
pip install -r requirements.txt
```

## Web app

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) for **選號**, or [http://localhost:5000/backtest](http://localhost:5000/backtest) for **復盤**.

Use the top nav to switch pages, and the **中文 / EN** toggle for language.

- **投注方式**: 單式 (6 numbers), 復式 (7–12 numbers), or 拖膽 (bankers + trailers)
- Strategy, draws to analyze, and how many suggestions to generate

Results show the latest HKJC draw, top-scored numbers, units/cost for 復式 & 拖膽, and colored balls.

## Deploy to Vercel (production)

Vercel supports Flask with zero configuration when `app.py` exports a variable named `app`.

### Option A: Deploy from GitHub (recommended)

1. Push this repo to GitHub.
2. Go to [vercel.com/new](https://vercel.com/new) and import the repository.
3. Vercel auto-detects Flask. Leave **Build Command** and **Output Directory** empty.
4. Click **Deploy**.

Your site will be live at `https://your-project.vercel.app`.

### Option B: Deploy with the Vercel CLI

```bash
npm i -g vercel
cd c:\Users\Sin\Documents\GitHub\MarkSix
vercel
```

Follow the prompts. Use `vercel --prod` for production.

### Production notes

- **vercel.json**: Not required. Vercel auto-detects Flask from `app.py` (zero-config).
- **Cache**: On Vercel, draw cache is stored in `/tmp` (per server instance, not permanent). First request after a cold start may take a few seconds while HKJC data is fetched.
- **Cold starts**: Serverless functions can have a short delay when idle.
- **Dependencies**: `requirements.txt` is installed automatically during deploy.
- **No `app.run()` on Vercel**: Vercel runs the Flask `app` as a serverless function; you do not need to start a local server in production.

## CLI

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
2. Scores each number (1-49) using frequency, gap analysis, pair co-occurrence, and draw balance patterns
3. Generates ticket combinations that score highly while matching typical draw structure

## Disclaimer

Mark Six is a game of chance. Each draw is independent and every combination has the same true probability. This tool identifies patterns in past data for entertainment and analysis - it does **not** guarantee wins or beat the odds.
