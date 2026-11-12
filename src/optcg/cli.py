"""Command line: `optcg cards`, `optcg sim`, `optcg show`."""

from __future__ import annotations

import argparse
import random
from collections import Counter
from pathlib import Path

from optcg.agents import AGENTS
from optcg.cards import load_cards
from optcg.engine import new_game
from optcg.loader import Source, fetch_set, write_set
from optcg.sim import play_game, random_deck, run_match

DATA = Path("data/cards")


def cmd_cards(args: argparse.Namespace) -> None:
    cards = fetch_set(args.set, Source(local=args.local, lang=args.lang))
    out = DATA / f"{args.set}.json"
    write_set(cards, out)
    print(f"wrote {len(cards)} cards to {out}")
    print("  by category:", dict(Counter(c.category for c in cards)))
    print("  by rarity:  ", dict(Counter(c.rarity for c in cards)))
    kw = Counter(k for c in cards for k in c.keywords)
    print("  keywords:   ", dict(kw))


def _setup(args: argparse.Namespace):
    cards = list(load_cards(DATA / f"{args.set}.json").values())
    rng = random.Random(args.seed)
    leaders = [c for c in cards if c.category == "Leader"]
    leader_pair = (rng.choice(leaders), rng.choice(leaders))
    decks = (random_deck(cards, rng), random_deck(cards, rng))
    return leader_pair, decks


def cmd_sim(args: argparse.Namespace) -> None:
    leaders, decks = _setup(args)
    a0, a1 = AGENTS[args.p0], AGENTS[args.p1]
    results = run_match(lambda seed: (a0(), a1()), leaders, decks, args.games, args.seed)
    wins = Counter(r.winner for r in results)
    n = len(results)
    first_wins = sum(1 for r in results if r.winner == r.first)
    avg_turns = sum(r.turns for r in results) / n
    print(f"{n} games, {args.p0} (P0) vs {args.p1} (P1)")
    print(f"  P0 wins {wins[0]} ({wins[0] / n:.1%}), P1 wins {wins[1]}, draws {wins[None]}")
    print(f"  going first wins {first_wins / n:.1%}, avg game length {avg_turns:.1f} turns")


def cmd_show(args: argparse.Namespace) -> None:
    """Play one game with a full log, for eyeballing the rules."""
    leaders, decks = _setup(args)
    s = new_game(leaders, decks, seed=args.seed, log=True)
    play_game(s, (AGENTS[args.p0](), AGENTS[args.p1]()))
    print("\n".join(s.log))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="optcg")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("cards", help="download a set from punk-records into data/cards/")
    c.add_argument("--set", default="OP-17")
    c.add_argument("--lang", default="english")
    c.add_argument("--local", help="path to a local punk-records clone instead of GitHub")
    c.set_defaults(func=cmd_cards)

    for name, func, help_ in (
        ("sim", cmd_sim, "play many games and report win rates"),
        ("show", cmd_show, "play one logged game"),
    ):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--set", default="OP-17")
        p.add_argument("--p0", default="heuristic", choices=sorted(AGENTS))
        p.add_argument("--p1", default="random", choices=sorted(AGENTS))
        p.add_argument("--seed", type=int, default=0)
        if name == "sim":
            p.add_argument("--games", type=int, default=200)
        p.set_defaults(func=func)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
