import random
from collections import Counter

import pytest

from optcg.cards import CardDef
from optcg.deckbuilder import BuildConfig, build_deck, stat_value
from optcg.packs import PackModel, PackSampler

SET_SIZES = {
    "Leader": 6,
    "Common": 45,
    "Uncommon": 30,
    "Rare": 26,
    "SuperRare": 10,
    "SecretRare": 2,
}


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
                )
            )
    return cards


@pytest.fixture
def model():
    return PackModel.load("config/pack_model.toml")


@pytest.fixture
def sampler(model):
    return PackSampler(fake_set(), model, random.Random(7))


def test_pack_shape(sampler, model):
    for _ in range(50):
        pack = sampler.open_pack()
        assert len(pack) == model.cards_per_pack
        r = Counter(c.rarity for c in pack)
        assert r["Uncommon"] == 3 and r["Rare"] == 1
        assert r["Common"] in (7, 8) and r["Leader"] in (0, 1)
        assert len({c.id for c in pack}) == len(pack)  # no duplicates within a pack


def test_box_hits_are_scheduled(sampler, model):
    for _ in range(30):
        box = sampler.open_box()
        assert len(box) == model.packs_per_box
        srs = [c for p in box for c in p if c.rarity == "SuperRare"]
        assert len(srs) in model.super_rares_per_box
        assert len({c.id for c in srs}) == len(srs)  # a box's SRs are different cards
        assert all(sum(c.rarity == "SuperRare" for c in p) <= 1 for p in box)
        assert all(
            sum(c.rarity == "Rare" for c in p)
            + sum(c.rarity in ("SuperRare", "SecretRare") for c in p)
            == 1
            for p in box
        )


def test_case_secret_rares(sampler, model):
    case = sampler.open_case()
    assert len(case) == model.boxes_per_case
    secrets = sum(c.rarity == "SecretRare" for box in case for p in box for c in p)
    assert secrets == model.secret_rares_per_case


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


def test_deck_is_legal_and_follows_curve(sampler, model):
    cfg = BuildConfig()
    for pool in sampler.event_pools(20):
        leader, deck = build_deck(pool, model.fallback_leader(), cfg=cfg)
        assert leader.category == "Leader" and len(deck) == cfg.deck_size
        assert not Counter(c.id for c in deck) - Counter(c.id for c in pool)  # only pool cards
        assert all(c.category != "Leader" for c in deck)
        assert sum((c.cost or 0) <= cfg.cheap_cost for c in deck) >= min(
            cfg.min_cheap,
            sum((c.cost or 0) <= cfg.cheap_cost for c in pool if c.category != "Leader"),
        )
        assert sum((c.cost or 0) >= cfg.expensive_cost for c in deck) <= cfg.max_expensive


def test_values_override_heuristic(model):
    pool = [c for c in fake_set() if c.rarity in ("Common", "Uncommon")][:60]
    target = min(pool, key=stat_value)
    _, deck = build_deck(pool, model.fallback_leader(), values={target.id: 99.0})
    assert target in deck


def test_fallback_leader_when_pool_has_none(model):
    pool = [c for c in fake_set() if c.category != "Leader"][:50]
    leader, _ = build_deck(pool, model.fallback_leader())
    assert leader.id == "EVENT-LEADER"
