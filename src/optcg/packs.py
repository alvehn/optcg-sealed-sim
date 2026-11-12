"""Open booster product the way a store does: case -> box -> pack.

Hits are scheduled per box rather than rolled per pack, so a box's SuperRare count stays
inside a narrow range, and a player whose 6 packs come from one box gets correlated hits.
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
HIT_SLOT = "Rare"  # the slot a SuperRare / SecretRare replaces


@dataclass(frozen=True)
class PackModel:
    cards_per_pack: int
    packs_per_box: int
    boxes_per_case: int
    slots: dict[str, int]
    flex: dict[str, float]
    super_rares_per_box: dict[int, float]
    secret_rares_per_case: int
    packs_per_player: int = 6
    fallback_leader_life: int = 5
    fallback_leader_power: int = 5000

    def __post_init__(self):
        fixed = sum(self.slots.values())
        if fixed + (1 if self.flex else 0) != self.cards_per_pack:
            raise ValueError(f"slots ({fixed}) + flex don't add up to {self.cards_per_pack} cards")
        if self.slots.get(HIT_SLOT, 0) < 1:
            raise ValueError(f"packs need a {HIT_SLOT} slot for hits to replace")

    @classmethod
    def load(cls, path: str | Path = DEFAULT_MODEL) -> PackModel:
        with open(path, "rb") as f:
            d = tomllib.load(f)
        event = d.get("event", {})
        return cls(
            cards_per_pack=d["cards_per_pack"],
            packs_per_box=d["packs_per_box"],
            boxes_per_case=d["boxes_per_case"],
            slots=dict(d["slots"]),
            flex=dict(d.get("flex", {})),
            super_rares_per_box={int(k): v for k, v in d["box"]["super_rares"].items()},
            secret_rares_per_case=d["case"]["secret_rares"],
            packs_per_player=event.get("packs_per_player", 6),
            fallback_leader_life=event.get("fallback_leader_life", 5),
            fallback_leader_power=event.get("fallback_leader_power", 5000),
        )

    def fallback_leader(self) -> CardDef:
        return CardDef(
            id="EVENT-LEADER",
            name="Event Leader",
            category="Leader",
            life=self.fallback_leader_life,
            power=self.fallback_leader_power,
        )


class PackSampler:
    def __init__(self, cards: list[CardDef], model: PackModel, rng: random.Random):
        self.model = model
        self.rng = rng
        self.by_rarity: dict[str, list[CardDef]] = {}
        for c in cards:
            self.by_rarity.setdefault(c.rarity or "", []).append(c)
        needed = set(model.slots) | set(model.flex) | {"SuperRare", "SecretRare"}
        missing = [r for r in needed if not self.by_rarity.get(r)]
        if missing:
            raise ValueError(f"set has no cards of rarity {missing}")
        self._queue: list[Pack] = []  # unopened packs from the current case, in hand-out order

    def open_case(self) -> list[Box]:
        m = self.model
        secret_boxes = self.rng.sample(
            range(m.boxes_per_case), min(m.secret_rares_per_case, m.boxes_per_case)
        )
        return [self.open_box(secret_rares=int(i in secret_boxes)) for i in range(m.boxes_per_case)]

    def open_box(self, secret_rares: int = 0) -> Box:
        m = self.model
        counts, weights = zip(*m.super_rares_per_box.items(), strict=True)
        n_sr = self.rng.choices(counts, weights)[0]
        hit_packs = self.rng.sample(range(m.packs_per_box), n_sr + secret_rares)
        hits = self._distinct("SuperRare", n_sr) + self._distinct("SecretRare", secret_rares)
        hit_for = dict(zip(hit_packs, hits, strict=True))
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
