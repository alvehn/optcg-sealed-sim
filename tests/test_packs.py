import random
from collections import Counter
from pathlib import Path

import pytest

from optcg.cards import CardDef, load_cards
from optcg.deckbuilder import BuildConfig, build_deck, stat_value
from optcg.event import load_leader
from optcg.packs import PackModel, PackSampler, hit_tiers, playable

SET_SIZES = {
    "Leader": 6,
    "Common": 45,
    "Uncommon": 30,
    "Rare": 26,
    "SuperRare": 10,
    "SecretRare": 2,
}
# Parallels on the fake set, so every case-hit tier has printings to draw from.
PARALLELS = {
    ("Leader", 0): ("Leader",),
    ("Rare", 0): ("Rare",),
    ("SuperRare", 0): ("SuperRare", "Special"),
    ("SuperRare", 1): ("SuperRare",),
    ("Common", 0): ("TreasureRare",),
}
REAL_SET = Path("data/cards/OP-18.json")


def fake_set():
    cards = []
    for rarity, n in SET_SIZES.items():
        for i in range(n):
            category = "Leader" if rarity == "Leader" else "Character"
            cost = None if category == "Leader" else 1 + i % 9
            cards.append(
                CardDef(
                    id=f"{rarity}-{i}",
                    name=f"{rarity} {i}",
                    category=category,
                    cost=cost,
                    power=5000 if category == "Leader" else 1000 * (1 + i % 9),
                    counter=1000 if i % 2 else None,
                    life=5 if category == "Leader" else None,
                    rarity=rarity,
                    parallels=PARALLELS.get((rarity, i), ()),
                )
            )
    # Reprint SP inserts from an older set, one with a SecretRare-rarity printing.
    cards.append(
        CardDef(
            id="OLD-1",
            name="Old 1",
            category="Character",
            cost=3,
            power=4000,
            rarity="Special",
            parallels=("Special",),
            reprint=True,
        )
    )
    cards.append(
        CardDef(
            id="OLD-2",
            name="Old 2",
            category="Character",
            cost=9,
            power=9000,
            rarity="SecretRare",
            parallels=("SecretRare",) * 2,
            reprint=True,
        )
    )
    return cards


@pytest.fixture
def model():
    return PackModel.load("config/pack_model.toml")


@pytest.fixture
def sampler(model):
    return PackSampler(fake_set(), model, random.Random(7))


@pytest.fixture
def leader():
    return load_leader("data/leaders/event_luffy.json")[0]


HITS = ("Rare", "SuperRare", "SecretRare", "Special")


def test_pack_shape(sampler, model):
    for _ in range(50):
        pack = sampler.open_pack()
        assert len(pack) == model.cards_per_pack
        r = Counter(c.rarity for c in pack)
        assert r["Uncommon"] == 3 and r["Rare"] == 2
        assert r["Common"] in (6, 7) and r["Leader"] in (0, 1)
        assert len({c.id for c in pack}) == len(pack)  # no duplicates within a pack


def test_reprints_only_come_out_as_hits(sampler):
    assert all(not c.reprint for cards in sampler.by_rarity.values() for c in cards)
    assert [c.id for c in sampler.by_rarity["SecretRare"]] == ["SecretRare-0", "SecretRare-1"]
    special = Counter(c.id for c in sampler.tiers["special"])
    assert special == {"SuperRare-0": 1, "OLD-1": 1, "OLD-2": 2}


def test_alt_art_tier_has_one_entry_per_printing():
    tiers = hit_tiers(fake_set())
    assert Counter(c.id for c in tiers["alt_art"]) == {
        "Leader-0": 1,
        "Rare-0": 1,
        "SuperRare-0": 1,
        "SuperRare-1": 1,
    }
    assert [c.id for c in tiers["treasure_rare"]] == ["Common-0"]


def test_box_hits_are_scheduled(sampler, model):
    for _ in range(30):
        box = sampler.open_box()
        assert len(box) == model.packs_per_box
        srs = [c for p in box for c in p if c.rarity == "SuperRare"]
        assert len(srs) in model.super_rares_per_box
        assert len({c.id for c in srs}) == len(srs)  # a box's SRs are different cards
        # exactly one hit slot per pack: two cards of Rare-or-better rarity
        assert all(sum(c.rarity in HITS for c in p) == 2 for p in box)


def test_case_hit_counts(sampler, model):
    for _ in range(50):
        boxes = sampler.schedule_case()
        assert len(boxes) == model.boxes_per_case
        per_tier = Counter(tier for b in boxes for tier, _ in b.values())
        for tier, counts in model.case_hits.items():
            assert per_tier[tier] in counts, tier
    case = sampler.open_case()
    assert len(case) == model.boxes_per_case
    for box in case:
        for p in box:
            r = Counter(c.rarity for c in p)
            # the fixed slots survive; only the hit slot (one of the two Rares) changes
            assert len(p) == model.cards_per_pack and r["Uncommon"] == 3 and r["Rare"] >= 1


def test_event_pools_are_six_packs(sampler, model):
    pools = sampler.event_pools(9)
    assert len(pools) == 9
    assert all(len(p) == model.packs_per_player * model.cards_per_pack for p in pools)


def test_same_seed_same_pools(model):
    a = PackSampler(fake_set(), model, random.Random(3)).event_pools(4)
    b = PackSampler(fake_set(), model, random.Random(3)).event_pools(4)
    assert [[c.id for c in p] for p in a] == [[c.id for c in p] for p in b]


def test_bad_model_is_rejected(model):
    with pytest.raises(ValueError):
        PackModel(**{**model.__dict__, "cards_per_pack": 13})
    with pytest.raises(ValueError):
        PackModel(**{**model.__dict__, "case_hits": {"gold_don": (3,)}})


def test_deck_is_legal_and_follows_curve(sampler, leader):
    cfg = BuildConfig()
    for pool in sampler.event_pools(20):
        got_leader, deck = build_deck(pool, leader, cfg=cfg)
        assert got_leader is leader and len(deck) == cfg.deck_size
        assert not Counter(c.id for c in deck) - Counter(c.id for c in pool)  # only pool cards
        assert all(c.category != "Leader" for c in deck)
        assert sum((c.cost or 0) <= cfg.cheap_cost for c in deck) >= min(
            cfg.min_cheap,
            sum((c.cost or 0) <= cfg.cheap_cost for c in playable(pool)),
        )
        assert sum((c.cost or 0) >= cfg.expensive_cost for c in deck) <= cfg.max_expensive


def test_pool_leaders_are_never_used(sampler, leader):
    pools = [p for p in sampler.event_pools(40) if any(c.category == "Leader" for c in p)]
    assert pools
    for pool in pools:
        got, deck = build_deck(pool, leader)
        assert got.id == "EVENT-LUFFY-4TH"
        assert all(c.category != "Leader" for c in deck)


def test_values_override_heuristic(leader):
    pool = [c for c in fake_set() if c.rarity in ("Common", "Uncommon")][:60]
    target = min(pool, key=stat_value)
    _, deck = build_deck(pool, leader, values={target.id: 99.0})
    assert target in deck


@pytest.mark.skipif(not REAL_SET.exists(), reason="run `make cards SET=OP-18` first")
def test_real_op18_set(model):
    cards = list(load_cards(REAL_SET).values())
    sampler = PackSampler(cards, model, random.Random(0))
    alt = Counter(c.rarity for c in sampler.tiers["alt_art"])
    assert alt == {"SuperRare": 12, "Rare": 9, "Leader": 7}  # 25% L / 43% SR / 32% R
    assert [c.id for c in sampler.tiers["treasure_rare"]] == ["OP18-049"]  # English TR
    sizes = [len(playable(p)) for p in sampler.event_pools(96)]
    assert 60 <= min(sizes) and max(sizes) <= 72
