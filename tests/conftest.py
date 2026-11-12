import pytest

from optcg.cards import CardDef


def leader(life: int = 5, power: int = 5000) -> CardDef:
    return CardDef(id="T-L", name="Test Leader", category="Leader", life=life, power=power)


def char(cost=2, power=3000, counter=1000, keywords=(), name=None) -> CardDef:
    return CardDef(
        id=f"T-{cost}-{power}-{'-'.join(keywords)}",
        name=name or f"Char {cost}/{power}",
        category="Character",
        cost=cost,
        power=power,
        counter=counter,
        keywords=frozenset(keywords),
    )


@pytest.fixture
def vanilla_deck():
    return [char(c, 1000 + 1000 * c) for c in (1, 2, 3, 4, 5) for _ in range(8)]
