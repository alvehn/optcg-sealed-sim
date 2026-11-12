"""Command line: `optcg cards | sim | show | pool | sealed`."""

from __future__ import annotations

import argparse
import random
from collections import Counter
from pathlib import Path

from optcg.agents import AGENTS
from optcg.cards import load_cards
from optcg.deckbuilder import build_deck, curve
from optcg.engine import new_game
from optcg.loader import Source, fetch_set, write_set
from optcg.packs import PackModel, PackSampler
from optcg.sim import play_game, random_deck, run_match, run_sealed

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
    _report(results, args)


def cmd_show(args: argparse.Namespace) -> None:
    """Play one game with a full log, for eyeballing the rules."""
    leaders, decks = _setup(args)
    s = new_game(leaders, decks, seed=args.seed, log=True)
    play_game(s, (AGENTS[args.p0](), AGENTS[args.p1]()))
    print("\n".join(s.log))


def _sampler(args: argparse.Namespace) -> PackSampler:
    cards = list(load_cards(DATA / f"{args.set}.json").values())
    return PackSampler(cards, PackModel.load(args.packs), random.Random(args.seed))


def cmd_pool(args: argparse.Namespace) -> None:
    """Open one sealed pool and show the deck built from it."""
    sampler = _sampler(args)
    pool = sampler.event_pools(1)[0]
    leader, deck = build_deck(pool, sampler.model.fallback_leader())
    order = ["SecretRare", "SuperRare", "Leader", "Rare", "Uncommon", "Common"]
    print(f"Pool: {len(pool)} cards")
    for rarity in order:
        names = sorted(c.name for c in pool if c.rarity == rarity)
        if names:
            print(f"  {rarity:<10} {len(names):>2}  {', '.join(names)}")
    print(f"\nLeader: {leader.name} ({leader.life} life, {leader.power} power)")
    print(f"Deck: {len(deck)} cards, curve {curve(deck)}")
    print(
        f"  counters: {sum(1 for c in deck if c.counter)} cards, "
        f"blockers: {sum(1 for c in deck if c.has('Blocker'))}"
    )
    for name, n in sorted(
        Counter(f"{c.cost} {c.name}" for c in deck).items(),
        key=lambda kv: (int(kv[0].split()[0] or 0), kv[0]),
    ):
        print(f"  {n}x {name}")


def cmd_sealed(args: argparse.Namespace) -> None:
    sampler = _sampler(args)
    a0, a1 = AGENTS[args.p0], AGENTS[args.p1]
    results = run_sealed(sampler, lambda seed: (a0(), a1()), args.games, args.seed)
    _report(results, args)


def _report(results, args: argparse.Namespace) -> None:
    wins = Counter(r.winner for r in results)
    n = len(results)
    first_wins = sum(1 for r in results if r.winner == r.first)
    avg_turns = sum(r.turns for r in results) / n
    print(f"{n} games, {args.p0} (P0) vs {args.p1} (P1)")
    print(f"  P0 wins {wins[0]} ({wins[0] / n:.1%}), P1 wins {wins[1]}, draws {wins[None]}")
    print(f"  going first wins {first_wins / n:.1%}, avg game length {avg_turns:.1f} turns")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="optcg")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("cards", help="download a set from punk-records into data/cards/")
    c.add_argument("--set", default="OP-17")
    c.add_argument("--lang", default="english")
    c.add_argument("--local", help="path to a local punk-records clone instead of GitHub")
    c.set_defaults(func=cmd_cards)

    for name, func, help_ in (
        ("sim", cmd_sim, "play many games between two random decks"),
        ("show", cmd_show, "play one logged game"),
        ("pool", cmd_pool, "open one sealed pool and show the deck built from it"),
        ("sealed", cmd_sealed, "play games between freshly opened sealed decks"),
    ):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--set", default="OP-17")
        p.add_argument("--p0", default="heuristic", choices=sorted(AGENTS))
        p.add_argument("--p1", default="random", choices=sorted(AGENTS))
        p.add_argument("--seed", type=int, default=0)
        if name in ("sim", "sealed"):
            p.add_argument("--games", type=int, default=200)
        if name in ("pool", "sealed"):
            p.add_argument("--packs", default="config/pack_model.toml", help="pack model config")
        p.set_defaults(func=func)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
