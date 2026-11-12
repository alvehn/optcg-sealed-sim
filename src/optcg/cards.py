"""Card definitions: the static, printed data for a card."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Keywords the engine understands without an effect DSL.
KEYWORDS = ("Blocker", "Rush", "Double Attack", "Banish")

# "[Blocker]" printed as the card's own keyword, not "gains [Blocker]" granted by an effect.
_GRANTED = re.compile(r"\b(gains?|have|has)(\s+\[[^\]]+\](\s*(and|,))?)*$", re.IGNORECASE)


def parse_keywords(effect: str | None) -> frozenset[str]:
    """Return the static keywords on a card.

    A keyword counts only if it is the card's own (e.g. effect text starting with
    "[Blocker]"), not one granted conditionally ("this Character gains [Blocker]").
    """
    if not effect:
        return frozenset()
    found = set()
    for kw in KEYWORDS:
        for m in re.finditer(re.escape(f"[{kw}]"), effect):
            if not _GRANTED.search(effect[: m.start()].rstrip()):
                found.add(kw)
                break
    return frozenset(found)


@dataclass(frozen=True)
class CardDef:
    id: str
    name: str
    category: str  # Leader | Character | Event | Stage
    colors: tuple[str, ...] = ()
    cost: int | None = None
    power: int | None = None
    counter: int | None = None
    life: int | None = None  # leaders only
    types: tuple[str, ...] = ()
    attributes: tuple[str, ...] = ()
    effect: str | None = None
    trigger: str | None = None
    rarity: str | None = None
    keywords: frozenset[str] = field(default_factory=frozenset)
    variants: int = 1  # number of printed arts (base + parallels) in the set

    # Card definitions are immutable and shared, so game-state copies reuse them.
    def __deepcopy__(self, memo):
        return self

    def has(self, keyword: str) -> bool:
        return keyword in self.keywords

    def to_json(self) -> dict:
        d = asdict(self)
        d["keywords"] = sorted(self.keywords)
        return d

    @classmethod
    def from_json(cls, d: dict) -> CardDef:
        d = dict(d)
        for key in ("colors", "types", "attributes"):
            d[key] = tuple(d.get(key) or ())
        d["keywords"] = frozenset(d.get("keywords") or ())
        return cls(**d)


def load_cards(path: str | Path) -> dict[str, CardDef]:
    with open(path) as f:
        return {c["id"]: CardDef.from_json(c) for c in json.load(f)}
