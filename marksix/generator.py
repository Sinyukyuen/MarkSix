"""Generate Mark Six ticket suggestions from scored numbers."""

from __future__ import annotations

import random
from dataclasses import dataclass

from marksix.analysis import NumberStats, balance_score


@dataclass(frozen=True)
class Ticket:
    numbers: tuple[int, ...]
    special: int
    ticket_score: float
    balance: float
    strategy: str


def _weighted_pick(
    pool: list[NumberStats],
    count: int,
    rng: random.Random,
) -> list[int]:
    available = pool[:]
    chosen: list[int] = []
    while len(chosen) < count and available:
        weights = [max(item.composite_score, 0.01) for item in available]
        pick = rng.choices(available, weights=weights, k=1)[0]
        chosen.append(pick.number)
        available = [item for item in available if item.number != pick.number]
    return sorted(chosen)


def _best_greedy_ticket(
    stats: list[NumberStats],
    *,
    min_balance: float,
) -> list[int] | None:
    candidates = stats[:20]
    best: list[int] | None = None
    best_value = -1.0

    for index in range(len(candidates) - 5):
        ticket = [candidates[index].number]
        for item in candidates[index + 1 :]:
            if len(ticket) == 6:
                break
            trial = sorted(ticket + [item.number])
            if balance_score(trial) >= min_balance * 0.8:
                ticket.append(item.number)
        if len(ticket) < 6:
            continue
        ticket = sorted(ticket[:6])
        value = sum(
            next(stat.composite_score for stat in stats if stat.number == number)
            for number in ticket
        )
        value += balance_score(ticket) * 2.0
        if value > best_value:
            best_value = value
            best = ticket
    return best


def _pick_special(stats: list[NumberStats], main_numbers: set[int], rng: random.Random) -> int:
    pool = [item for item in stats if item.number not in main_numbers]
    return rng.choices(pool[:15], weights=[max(item.composite_score, 0.01) for item in pool[:15]], k=1)[0].number


def generate_tickets(
    stats: list[NumberStats],
    *,
    strategy: str,
    count: int = 5,
    seed: int | None = None,
    min_balance: float = 0.55,
) -> list[Ticket]:
    rng = random.Random(seed)
    tickets: list[Ticket] = []
    seen: set[tuple[int, ...]] = set()

    greedy = _best_greedy_ticket(stats, min_balance=min_balance)
    if greedy is not None:
        ticket_numbers = tuple(greedy)
        seen.add(ticket_numbers)
        tickets.append(
            Ticket(
                numbers=ticket_numbers,
                special=_pick_special(stats, set(ticket_numbers), rng),
                ticket_score=sum(
                    next(item.composite_score for item in stats if item.number == number)
                    for number in ticket_numbers
                ),
                balance=balance_score(list(ticket_numbers)),
                strategy=strategy,
            )
        )

    attempts = 0
    while len(tickets) < count and attempts < count * 200:
        attempts += 1
        numbers = _weighted_pick(stats, 6, rng)
        if len(numbers) != 6:
            continue
        balance = balance_score(numbers)
        if balance < min_balance:
            continue
        key = tuple(numbers)
        if key in seen:
            continue
        seen.add(key)
        tickets.append(
            Ticket(
                numbers=key,
                special=_pick_special(stats, set(numbers), rng),
                ticket_score=sum(
                    next(item.composite_score for item in stats if item.number == number)
                    for number in numbers
                ),
                balance=balance,
                strategy=strategy,
            )
        )

    tickets.sort(key=lambda item: (item.ticket_score, item.balance), reverse=True)
    return tickets[:count]
