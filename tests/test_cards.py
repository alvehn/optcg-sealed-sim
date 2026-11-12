from optcg.cards import CardDef, parse_keywords
from optcg.loader import normalize


def test_own_keywords_are_parsed():
    assert parse_keywords("[Blocker] (After your opponent declares an attack...)") == {"Blocker"}
    assert parse_keywords("[Rush] [Double Attack] [On Play] Draw 1 card.") == {
        "Rush",
        "Double Attack",
    }


def test_granted_keywords_are_not():
    assert (
        parse_keywords(
            "If there is a Character with a cost of 12 or more, "
            "this Character gains [Blocker] and +3000 power."
        )
        == set()
    )
    assert (
        parse_keywords("All of your Characters with a cost of 12 or more gain [Blocker].") == set()
    )
    assert (
        parse_keywords("[On Play] This Character gains [Rush] and [Banish] during this turn.")
        == set()
    )
    assert parse_keywords(None) == set()


def raw(id_, category="Character", cost=2, rarity="Common", **kw):
    return {
        "id": id_,
        "name": id_,
        "category": category,
        "cost": cost,
        "power": 3000,
        "counter": 1000,
        "colors": ["Red"],
        "types": [],
        "attributes": [],
        "effect": kw.get("effect"),
        "trigger": None,
        "rarity": rarity,
    }


def test_normalize_merges_parallels_and_drops_reprints():
    cards = normalize(
        [
            raw("OP17-001", category="Leader", cost=5, rarity="Leader"),
            raw("OP17-001_p1", category="Leader", cost=5, rarity="Leader"),
            raw("OP17-010_p1", rarity="SuperRare"),
            raw("OP17-010", rarity="Common", effect="[Blocker]"),
            raw("EB04-061_p2", rarity="SecretRare"),
        ],
        "OP-17",
    )
    by_id = {c.id: c for c in cards}
    assert set(by_id) == {"OP17-001", "OP17-010"}
    assert by_id["OP17-001"].life == 5 and by_id["OP17-001"].cost is None
    assert by_id["OP17-010"].rarity == "Common" and by_id["OP17-010"].variants == 2
    assert by_id["OP17-010"].has("Blocker")


def test_json_roundtrip():
    c = CardDef(
        id="X", name="X", category="Character", cost=1, types=("A",), keywords=frozenset({"Rush"})
    )
    assert CardDef.from_json(c.to_json()) == c
