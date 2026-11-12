"""Load card data from punk-records (https://github.com/buhbbl/punk-records).

punk-records is generated from the official card list by vegapull. Each pack is
`<lang>/data/<pack_id>.json`; `<lang>/packs.json` maps pack ids to labels such as "OP-17".
Parallel/alt-art printings have ids like "OP17-062_p1" and play exactly like the base card,
so they are merged into one CardDef with a `variants` count.
"""

from __future__ import annotations

import html
import json
import re
import urllib.request
from pathlib import Path

from optcg.cards import CardDef, parse_keywords

RAW_BASE = "https://raw.githubusercontent.com/buhbbl/punk-records/{branch}/{lang}/{path}"
_VARIANT = re.compile(r"_p\d+$")


class Source:
    """Reads punk-records files from a local clone or straight from GitHub."""

    def __init__(
        self, local: str | Path | None = None, lang: str = "english", branch: str = "main"
    ):
        self.local = Path(local) if local else None
        self.lang = lang
        self.branch = branch

    def read_json(self, path: str):
        if self.local:
            with open(self.local / self.lang / path) as f:
                return json.load(f)
        url = RAW_BASE.format(branch=self.branch, lang=self.lang, path=path)
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.load(resp)


def find_pack_id(source: Source, label: str) -> str:
    """Map a set label like "OP-17" to its punk-records pack id."""
    packs = source.read_json("packs.json")
    for pack_id, pack in packs.items():
        if (pack.get("title_parts") or {}).get("label") == label:
            return pack_id
    known = sorted(p["title_parts"]["label"] for p in packs.values() if p["title_parts"]["label"])
    raise KeyError(f"set {label!r} not in punk-records yet; known sets: {', '.join(known)}")


def normalize(raw_cards: list[dict], set_label: str) -> list[CardDef]:
    """Merge parallels into their base card and keep only cards printed in this set.

    Packs also contain reprinted SP cards from older sets (e.g. "EB04-061_p2" in OP-17);
    those are chase pulls rather than part of the set's rarity distribution, so they are dropped.
    """
    prefix = set_label.replace("-", "")  # "OP-17" -> "OP17"
    by_base: dict[str, list[dict]] = {}
    for c in raw_cards:
        base = _VARIANT.sub("", c["id"])
        if base.startswith(prefix + "-"):
            by_base.setdefault(base, []).append(c)

    cards = []
    for base, printings in sorted(by_base.items()):
        # Prefer the base printing: its rarity is the one that determines pull rates.
        c = next((p for p in printings if p["id"] == base), printings[0])
        is_leader = c["category"] == "Leader"
        cards.append(
            CardDef(
                id=base,
                name=_text(c["name"]),
                category=c["category"],
                colors=tuple(c.get("colors") or ()),
                # punk-records stores a leader's life in its "cost" field.
                cost=None if is_leader else c.get("cost"),
                life=c.get("cost") if is_leader else None,
                power=c.get("power"),
                counter=c.get("counter"),
                types=tuple(c.get("types") or ()),
                attributes=tuple(c.get("attributes") or ()),
                effect=_text(c.get("effect")),
                trigger=_text(c.get("trigger")),
                rarity=c.get("rarity"),
                keywords=parse_keywords(c.get("effect")),
                variants=len(printings),
            )
        )
    return cards


def _text(s: str | None) -> str | None:
    return html.unescape(s) if s else s


def fetch_set(set_label: str, source: Source | None = None) -> list[CardDef]:
    source = source or Source()
    pack_id = find_pack_id(source, set_label)
    return normalize(source.read_json(f"data/{pack_id}.json"), set_label)


def write_set(cards: list[CardDef], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump([c.to_json() for c in cards], f, indent=1, ensure_ascii=False)
