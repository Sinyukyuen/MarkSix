"""Fetch and cache Hong Kong Mark Six draw history from HKJC."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import requests

HKJC_GRAPHQL_URL = "https://info.cld.hkjc.com/graphql/base/"
CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "draws_cache.json"

GRAPHQL_QUERY = """fragment lotteryDrawsFragment on LotteryDraw {
    id
    year
    no
    openDate
    closeDate
    drawDate
    status
    snowballCode
    snowballName_en
    snowballName_ch
    lotteryPool {
        sell
        status
        totalInvestment
        jackpot
        unitBet
        estimatedPrize
        derivedFirstPrizeDiv
        lotteryPrizes {
            type
            winningUnit
            dividend
        }
    }
    drawResult {
        drawnNo
        xDrawnNo
    }
}

query marksixResult($lastNDraw: Int, $startDate: String, $endDate: String, $drawType: LotteryDrawType) {
    lotteryDraws(
        lastNDraw: $lastNDraw
        startDate: $startDate
        endDate: $endDate
        drawType: $drawType
    ) {
        ...lotteryDrawsFragment
    }
}"""

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Origin": "https://bet.hkjc.com",
    "Referer": "https://bet.hkjc.com/",
}


@dataclass(frozen=True)
class Draw:
    draw_id: str
    year: str
    draw_no: int
    draw_date: datetime
    numbers: tuple[int, ...]
    special: int


def _parse_draw_date(value: str) -> datetime:
    for fmt in ("%Y-%m-%d+08:00", "%Y-%m-%dT%H:%M:%S+08:00"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported draw date format: {value}")


def _to_draw(raw: dict) -> Draw | None:
    result = raw.get("drawResult") or {}
    numbers = result.get("drawnNo")
    special = result.get("xDrawnNo")
    if not numbers or special is None:
        return None

    cleaned = sorted(int(n) for n in numbers)
    if len(cleaned) != 6 or len(set(cleaned)) != 6:
        return None
    if not all(1 <= n <= 49 for n in cleaned):
        return None
    special = int(special)
    if not 1 <= special <= 49:
        return None

    return Draw(
        draw_id=str(raw["id"]),
        year=str(raw["year"]),
        draw_no=int(raw["no"]),
        draw_date=_parse_draw_date(raw["drawDate"]),
        numbers=tuple(cleaned),
        special=special,
    )


def _post_graphql(variables: dict) -> list[dict]:
    response = requests.post(
        HKJC_GRAPHQL_URL,
        json={
            "operationName": "marksixResult",
            "variables": variables,
            "query": GRAPHQL_QUERY,
        },
        headers=REQUEST_HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if "errors" in payload:
        raise RuntimeError(f"HKJC API error: {payload['errors']}")
    return payload["data"]["lotteryDraws"]


def fetch_recent_draws(count: int) -> list[Draw]:
    raw_draws = _post_graphql({"lastNDraw": count})
    return _normalize_draws(raw_draws)


def fetch_draws_by_date_range(start: datetime, end: datetime) -> list[Draw]:
    chunks: list[Draw] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=90), end)
        raw_draws = _post_graphql(
            {
                "startDate": cursor.strftime("%Y%m%d"),
                "endDate": chunk_end.strftime("%Y%m%d"),
            }
        )
        chunks.extend(_normalize_draws(raw_draws))
        cursor = chunk_end + timedelta(days=1)
    return _dedupe_draws(chunks)


def _normalize_draws(raw_draws: Iterable[dict]) -> list[Draw]:
    draws: list[Draw] = []
    for raw in raw_draws:
        draw = _to_draw(raw)
        if draw is not None:
            draws.append(draw)
    return _dedupe_draws(draws)


def _dedupe_draws(draws: Iterable[Draw]) -> list[Draw]:
    seen: set[str] = set()
    unique: list[Draw] = []
    for draw in draws:
        if draw.draw_id in seen:
            continue
        seen.add(draw.draw_id)
        unique.append(draw)
    unique.sort(key=lambda item: item.draw_date, reverse=True)
    return unique


def load_cached_draws() -> list[Draw]:
    if not CACHE_PATH.exists():
        return []
    with CACHE_PATH.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return [
        Draw(
            draw_id=item["draw_id"],
            year=item["year"],
            draw_no=item["draw_no"],
            draw_date=datetime.fromisoformat(item["draw_date"]),
            numbers=tuple(item["numbers"]),
            special=item["special"],
        )
        for item in payload
    ]


def save_cached_draws(draws: list[Draw]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "draw_id": draw.draw_id,
            "year": draw.year,
            "draw_no": draw.draw_no,
            "draw_date": draw.draw_date.isoformat(),
            "numbers": list(draw.numbers),
            "special": draw.special,
        }
        for draw in draws
    ]
    with CACHE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def get_draw_history(
    *,
    lookback_draws: int = 300,
    refresh: bool = False,
    use_cache: bool = True,
) -> list[Draw]:
    if use_cache and not refresh:
        cached = load_cached_draws()
        if len(cached) >= lookback_draws:
            return cached[:lookback_draws]

    draws = fetch_recent_draws(lookback_draws)
    if len(draws) < lookback_draws:
        end = datetime.now()
        start = end - timedelta(days=365 * 3)
        draws = fetch_draws_by_date_range(start, end)
        draws = draws[:lookback_draws]

    if use_cache and draws:
        save_cached_draws(draws)

    return draws
