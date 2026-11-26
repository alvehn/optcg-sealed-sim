"""Command line: `optcg cards | sim | show | pool | pools | sealed`."""

from __future__ import annotations

import argparse
import csv
import random
from collections import Counter
from pathlib import Path

from optcg.agents import AGENTS
from optcg.cards import load_cards
from optcg.deckbuilder import build_deck, curve
from optcg.engine import new_game
from optcg.event import EventConfig, load_leader
from optcg.loader import Source, fetch_set, write_set
from optcg.packs import PackModel, PackSampler, playable
from optcg.sim import play_game, random_deck, run_match, run_sealed

DATA = Path("data/cards")
LOGS = Path("data/logs")


def cmd_cards(args: argparse.Namespace) -> None:
    cards = fetch_set(args.set, Source(local=args.local, lang=args.lang), pack_id=args.pack_id)
    out = DATA / f"{args.set}.json"
    write_set(cards, out)
    own = [c for c in cards if not c.reprint]
    print(f"wrote {len(own)} set cards + {len(cards) - len(own)} reprints to {out}")
    print("  by category:", dict(Counter(c.category for c in own)))
    print("  by rarity:  ", dict(Counter(c.rarity for c in own)))
    print("  parallels:  ", dict(Counter(r for c in cards for r in c.parallels)))
    kw = Counter(k for c in cards for k in c.keywords)
    print("  keywords:   ", dict(kw))


def _leader(args: argparse.Namespace):
    return load_leader(EventConfig.load(args.event).leader)[0]


def _setup(args: argparse.Namespace):
    cards = list(load_cards(DATA / f"{args.set}.json").values())
    rng = random.Random(args.seed)
    leader = _leader(args)
    decks = (random_deck(cards, rng), random_deck(cards, rng))
    return (leader, leader), decks


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
    leader, deck = build_deck(pool, _leader(args))
    order = ["SecretRare", "Special", "SuperRare", "Leader", "Rare", "Uncommon", "Common"]
    print(f"Pool: {len(pool)} cards, {len(playable(pool))} playable (Leaders are not played)")
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


def cmd_pools(args: argparse.Namespace) -> None:
    """Open many events' worth of pools and report what a typical pool contains."""
    cards = load_cards(DATA / f"{args.set}.json")
    sampler = PackSampler(
        list(cards.values()), PackModel.load(args.packs), random.Random(args.seed)
    )
    n, sizes, rarity, contains, srs = 0, [], Counter(), Counter(), Counter()
    for _ in range(args.events):
        for pool in sampler.event_pools(args.players):
            deckable = playable(pool)
            n += 1
            sizes.append(len(deckable))
            rarity.update(c.rarity for c in pool)
            contains.update({c.id for c in deckable})
            srs[sum(c.rarity == "SuperRare" for c in deckable)] += 1
    print(f"{n} pools ({args.events} events x {args.players} players)")
    print(
        f"  playable cards per pool: mean {sum(sizes) / n:.2f}, min {min(sizes)}, max {max(sizes)}"
    )
    print(
        "  cards per pool by rarity: "
        + ", ".join(f"{r} {k / n:.2f}" for r, k in rarity.most_common())
    )
    print(
        "  pools by SuperRare count: "
        + ", ".join(f"{k}: {v / n:.1%}" for k, v in sorted(srs.items()))
    )
    by_rarity: dict[str, list[float]] = {}
    for cid, c in cards.items():
        if c.category != "Leader":
            by_rarity.setdefault(c.rarity or "", []).append(contains[cid] / n)
    print(
        "  chance a given card is in a pool: "
        + ", ".join(
            f"{r} {sum(v) / len(v):.1%}"
            for r, v in sorted(by_rarity.items(), key=lambda kv: -sum(kv[1]) / len(kv[1]))
        )
    )
    LOGS.mkdir(parents=True, exist_ok=True)
    out = LOGS / f"pool_rates_{args.set}.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["card", "name", "rarity", "reprint", "pool_rate"])
        for cid, c in sorted(cards.items()):
            if c.category != "Leader":
                w.writerow([cid, c.name, c.rarity, c.reprint, f"{contains[cid] / n:.4f}"])
    print(f"  per-card pool rates -> {out}")


def cmd_sealed(args: argparse.Namespace) -> None:
    sampler = _sampler(args)
    a0, a1 = AGENTS[args.p0], AGENTS[args.p1]
    results = run_sealed(sampler, lambda seed: (a0(), a1()), args.games, _leader(args), args.seed)
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
    c.add_argument("--set", default="OP-18")
    c.add_argument("--lang", default="english")
    c.add_argument("--local", help="path to a local punk-records clone instead of GitHub")
    c.add_argument("--pack-id", help="punk-records pack id, if packs.json doesn't list the set")
    c.set_defaults(func=cmd_cards)

    p = sub.add_parser("pools", help="sample many event pools and report pool statistics")
    p.add_argument("--set", default="OP-18")
    p.add_argument("--events", type=int, default=1000)
    p.add_argument("--players", type=int, default=24)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--packs", default="config/pack_model.toml", help="pack model config")
    p.set_defaults(func=cmd_pools)

    for name, func, help_ in (
        ("sim", cmd_sim, "play many games between two random decks"),
        ("show", cmd_show, "play one logged game"),
        ("pool", cmd_pool, "open one sealed pool and show the deck built from it"),
        ("sealed", cmd_sealed, "play games between freshly opened sealed decks"),
    ):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--set", default="OP-18")
        p.add_argument("--p0", default="heuristic", choices=sorted(AGENTS))
        p.add_argument("--p1", default="random", choices=sorted(AGENTS))
        p.add_argument("--seed", type=int, default=0)
        p.add_argument("--event", default="config/event.toml", help="event config (leader)")
        if name in ("sim", "sealed"):
            p.add_argument("--games", type=int, default=200)
        if name in ("pool", "sealed"):
            p.add_argument("--packs", default="config/pack_model.toml", help="pack model config")
        p.set_defaults(func=func)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
