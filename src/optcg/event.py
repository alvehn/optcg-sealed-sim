"""The release event: its fixed leader and its format.

Every simulated player uses the 4th Anniversary event Luffy. Leaders opened in packs are
never played. Luffy counts as having every card name, type and attribute for checks against
the Leader, but is not a Character; the effect system reads those flags from the leader file.
"""

from __future__ import annotations

import json
import math
import tomllib
from dataclasses import dataclass
from pathlib import Path

from optcg.cards import CardDef

DEFAULT_EVENT = Path("config/event.toml")


@dataclass(frozen=True)
class LeaderRules:
    matches_any_name: bool = False
    matches_any_type: bool = False
    matches_any_attribute: bool = False
    counts_as_character: bool = False


@dataclass(frozen=True)
class EventConfig:
    leader: Path
    min_players: int
    max_players: int
    match: str  # "bo1"
    rounds: str | int  # "auto" = ceil(log2(players))
    prize: str
    bye: str
    sideboard_between_rounds: bool

    @classmethod
    def load(cls, path: str | Path = DEFAULT_EVENT) -> EventConfig:
        with open(path, "rb") as f:
            d = tomllib.load(f)
        lo, hi = d["players"]
        return cls(
            leader=Path(d["leader"]),
            min_players=lo,
            max_players=hi,
            match=d["match"],
            rounds=d.get("rounds", "auto"),
            prize=d.get("prize", "undefeated"),
            bye=d.get("bye", "win"),
            sideboard_between_rounds=d.get("sideboard_between_rounds", False),
        )

    def rounds_for(self, players: int) -> int:
        return swiss_rounds(players) if self.rounds == "auto" else int(self.rounds)


def swiss_rounds(players: int) -> int:
    """Rounds after which exactly one player is still undefeated."""
    return max(1, math.ceil(math.log2(players)))


def load_leader(path: str | Path) -> tuple[CardDef, LeaderRules]:
    with open(path) as f:
        d = json.load(f)
    card = CardDef(
        id=d["id"],
        name=d["name"],
        category="Leader",
        colors=tuple(d.get("colors") or ()),
        life=d["life"],
        power=d["power"],
        effect=d.get("effect") or None,
    )
    return card, LeaderRules(**d.get("rules", {}))
