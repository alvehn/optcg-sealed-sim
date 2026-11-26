"""Build a sealed deck from a pool: 40 cards, no colour or copy limits.

The leader is fixed by the event (event Luffy, see optcg.event); Leaders opened in the pool
are never played. The greedy builder ranks cards by a value (a printed-stats heuristic by
default, or ratings learned from simulation) and fills the deck under curve constraints.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass

from optcg.cards import CardDef

KEYWORD_VALUE = {"Blocker": 1.5, "Rush": 1.0, "Double Attack": 1.5, "Banish": 0.5}


@dataclass(frozen=True)
class BuildConfig:
    deck_size: int = 40
    min_cheap: int = 14  # cards costing <= cheap_cost, so the deck has early plays
    cheap_cost: int = 3
    max_expensive: int = 6  # cards costing >= expensive_cost
    expensive_cost: int = 7
    # The engine can't resolve Events or Stages yet, so they only fill an otherwise short deck.
    playable_categories: frozenset[str] = frozenset({"Character"})


DEFAULT_BUILD = BuildConfig()


def stat_value(c: CardDef) -> float:
    """Printed-stats value: power above the usual curve, counter, and keywords.

    A vanilla cost-N Character usually has about (N + 1) * 1000 power.
    """
    if c.category != "Character":
        return 0.0
    cost = c.cost or 0
    v = ((c.power or 0) - 1000 * (cost + 1)) / 1000
    v += (c.counter or 0) / 1000
    v += sum(KEYWORD_VALUE.get(k, 0) for k in c.keywords)
    return v


def build_deck(
    pool: list[CardDef],
    leader: CardDef,
    values: Mapping[str, float] | None = None,
    cfg: BuildConfig = DEFAULT_BUILD,
) -> tuple[CardDef, list[CardDef]]:
    """Returns (leader, deck). `values` maps card id -> value and overrides the stat heuristic."""

    def value(c: CardDef) -> float:
        return values[c.id] if values and c.id in values else stat_value(c)

    main = [c for c in pool if c.category != "Leader"]
    playable = sorted(
        (c for c in main if c.category in cfg.playable_categories),
        key=lambda c: (-value(c), c.cost or 0, c.id),
    )

    deck: list[CardDef] = []
    taken: set[int] = set()  # indexes into `playable`, so each copy is taken once

    def take(i: int) -> None:
        deck.append(playable[i])
        taken.add(i)

    # 1. Early plays first: the best cheap cards up to the minimum.
    cheap = [i for i, c in enumerate(playable) if (c.cost or 0) <= cfg.cheap_cost]
    for i in cheap[: cfg.min_cheap]:
        take(i)

    # 2. Then by value, capping the top of the curve.
    expensive = sum(1 for c in deck if (c.cost or 0) >= cfg.expensive_cost)
    for i, c in enumerate(playable):
        if len(deck) >= cfg.deck_size:
            break
        if i in taken:
            continue
        if (c.cost or 0) >= cfg.expensive_cost:
            if expensive >= cfg.max_expensive:
                continue
            expensive += 1
        take(i)

    # 3. A short deck is filled with what is left: capped cards, then unplayable ones.
    rest = [c for i, c in enumerate(playable) if i not in taken]
    rest += [c for c in main if c.category not in cfg.playable_categories]
    deck.extend(rest[: cfg.deck_size - len(deck)])

    if len(deck) < cfg.deck_size:
        raise ValueError(f"pool has only {len(main)} non-leader cards, need {cfg.deck_size}")
    return leader, deck


def curve(deck: list[CardDef]) -> dict[int, int]:
    return dict(sorted(Counter(c.cost or 0 for c in deck).items()))
