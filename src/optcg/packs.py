"""Open booster product the way a store does: case -> box -> pack.

Hits are scheduled rather than rolled per pack. Each case gets counts of SecretRares, alt arts,
SPs and Treasure Rares placed in different packs, then each box gets a SuperRare count spread
over its remaining packs. Every pack has one hit slot (a Rare unless a hit lands there).
A player's 6 packs come consecutively from one box, so hits are correlated within a box.

A hit is the playable card it prints: an alt art of a Rare is that Rare, an alt-art Leader is
a Leader (which the deckbuilder never plays), and an SP of an older card is that reprint.
"""

from __future__ import annotations

import random
import tomllib
from dataclasses import dataclass
from pathlib import Path

from optcg.cards import CardDef

Pack = list[CardDef]
Box = list[Pack]

DEFAULT_MODEL = Path("config/pack_model.toml")
HIT_SLOT = "Rare"  # the slot a hit replaces
CASE_TIERS = ("secret_rare", "alt_art", "special", "treasure_rare")
ALT_ART_RARITIES = ("Leader", "SuperRare", "Rare")


@dataclass(frozen=True)
class PackModel:
    cards_per_pack: int
    packs_per_box: int
    boxes_per_case: int
    slots: dict[str, int]
    flex: dict[str, float]
    super_rares_per_box: dict[int, float]
    case_hits: dict[str, tuple[int, ...]]  # tier -> possible counts per case (uniform)
    packs_per_player: int = 6

    def __post_init__(self):
        fixed = sum(self.slots.values())
        if fixed + (1 if self.flex else 0) != self.cards_per_pack:
            raise ValueError(f"slots ({fixed}) + flex don't add up to {self.cards_per_pack} cards")
        if self.slots.get(HIT_SLOT, 0) < 1:
            raise ValueError(f"packs need a {HIT_SLOT} slot for hits to replace")
        unknown = set(self.case_hits) - set(CASE_TIERS)
        if unknown:
            raise ValueError(f"unknown case hit tiers {sorted(unknown)}; known: {CASE_TIERS}")
        most = max(self.super_rares_per_box) * self.boxes_per_case + sum(
            max(v) for v in self.case_hits.values()
        )
        if most > self.packs_per_box * self.boxes_per_case:
            raise ValueError("more hits scheduled than packs in a case")

    @classmethod
    def load(cls, path: str | Path = DEFAULT_MODEL) -> PackModel:
        with open(path, "rb") as f:
            d = tomllib.load(f)
        return cls(
            cards_per_pack=d["cards_per_pack"],
            packs_per_box=d["packs_per_box"],
            boxes_per_case=d["boxes_per_case"],
            slots=dict(d["slots"]),
            flex=dict(d.get("flex", {})),
            super_rares_per_box={int(k): v for k, v in d["box"]["super_rares"].items()},
            case_hits={k: tuple(v) for k, v in d.get("case", {}).items()},
            packs_per_player=d.get("event", {}).get("packs_per_player", 6),
        )


def hit_tiers(cards: list[CardDef]) -> dict[str, list[CardDef]]:
    """Cards each case-hit tier draws from, one entry per printing (so more arts = likelier)."""
    tiers: dict[str, list[CardDef]] = {t: [] for t in CASE_TIERS}
    for c in cards:
        if not c.reprint and c.rarity == "SecretRare":
            tiers["secret_rare"].append(c)
        for r in c.parallels:
            if c.reprint or r == "Special":
                tiers["special"].append(c)
            elif r == "TreasureRare":
                tiers["treasure_rare"].append(c)
            elif r in ALT_ART_RARITIES:
                tiers["alt_art"].append(c)
    return tiers


class PackSampler:
    def __init__(self, cards: list[CardDef], model: PackModel, rng: random.Random):
        self.model = model
        self.rng = rng
        self.by_rarity: dict[str, list[CardDef]] = {}
        for c in cards:
            if not c.reprint:  # reprints only come out as SP hits
                self.by_rarity.setdefault(c.rarity or "", []).append(c)
        needed = set(model.slots) | set(model.flex) | {"SuperRare"}
        missing = [r for r in needed if not self.by_rarity.get(r)]
        if missing:
            raise ValueError(f"set has no cards of rarity {missing}")
        self.tiers = hit_tiers(cards)
        empty = [t for t, n in model.case_hits.items() if max(n) > 0 and not self.tiers[t]]
        if empty:
            raise ValueError(f"set has no printings for case hit tiers {empty}")
        self._queue: list[Pack] = []  # unopened packs from the current case, in hand-out order

    def schedule_case(self) -> list[dict[int, tuple[str, CardDef]]]:
        """For each box of a case: pack index -> (tier, card) for the case-level hits."""
        m = self.model
        spots = [(b, p) for b in range(m.boxes_per_case) for p in range(m.packs_per_box)]
        self.rng.shuffle(spots)
        boxes: list[dict[int, tuple[str, CardDef]]] = [{} for _ in range(m.boxes_per_case)]
        for tier, counts in m.case_hits.items():
            for _ in range(self.rng.choice(counts)):
                b, p = spots.pop()
                boxes[b][p] = (tier, self.rng.choice(self.tiers[tier]))
        return boxes

    def open_case(self) -> list[Box]:
        return [self.open_box({p: c for p, (_, c) in h.items()}) for h in self.schedule_case()]

    def open_box(self, case_hits: dict[int, CardDef] | None = None) -> Box:
        """A box: its share of the case hits plus its own SuperRares in other packs."""
        m = self.model
        hit_for = dict(case_hits or {})
        counts, weights = zip(*m.super_rares_per_box.items(), strict=True)
        n_sr = self.rng.choices(counts, weights)[0]
        free = [i for i in range(m.packs_per_box) if i not in hit_for]
        sr_packs = self.rng.sample(free, n_sr)
        hit_for.update(zip(sr_packs, self._distinct("SuperRare", n_sr), strict=True))
        return [self.open_pack(hit_for.get(i)) for i in range(m.packs_per_box)]

    def open_pack(self, hit: CardDef | None = None) -> Pack:
        pack: Pack = []
        for rarity, count in self.model.slots.items():
            if rarity == HIT_SLOT and hit is not None:
                pack.append(hit)
                count -= 1
            pack.extend(self._distinct(rarity, count, exclude=pack))
        if self.model.flex:
            rarities, weights = zip(*self.model.flex.items(), strict=True)
            rarity = self.rng.choices(rarities, weights)[0]
            pack.extend(self._distinct(rarity, 1, exclude=pack))
        return pack

    def _distinct(self, rarity: str, n: int, exclude: Pack = ()) -> list[CardDef]:
        """n different cards of a rarity, avoiding `exclude` while the rarity has enough."""
        pool = [c for c in self.by_rarity[rarity] if c not in exclude] or self.by_rarity[rarity]
        if n <= len(pool):
            return self.rng.sample(pool, n)
        return [self.rng.choice(pool) for _ in range(n)]

    def event_pools(self, players: int) -> list[list[CardDef]]:
        """Sealed pools of consecutive packs, as a store hands out a case box by box."""
        per = self.model.packs_per_player
        pools: list[list[CardDef]] = []
        while len(pools) < players:
            if len(self._queue) < per:
                for box in self.open_case():
                    self.rng.shuffle(box)
                    self._queue.extend(box)
            pools.append([c for p in self._queue[:per] for c in p])
            del self._queue[:per]
        return pools


def playable(pool: list[CardDef]) -> list[CardDef]:
    """The cards a sealed player can put in their deck: everything but Leaders."""
    return [c for c in pool if c.category != "Leader"]
