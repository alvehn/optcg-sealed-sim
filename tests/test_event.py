from optcg.event import EventConfig, load_leader, swiss_rounds


def test_event_leader():
    card, rules = load_leader("data/leaders/event_luffy.json")
    assert (card.category, card.life, card.power) == ("Leader", 5, 5000)
    assert rules.matches_any_name and rules.matches_any_type and rules.matches_any_attribute
    assert not rules.counts_as_character


def test_event_config():
    cfg = EventConfig.load("config/event.toml")
    assert (cfg.min_players, cfg.max_players, cfg.match) == (16, 32, "bo1")
    assert cfg.leader.name == "event_luffy.json"
    assert cfg.rounds_for(16) == 4 and cfg.rounds_for(24) == 5 and cfg.rounds_for(32) == 5


def test_swiss_rounds_leave_one_undefeated():
    for n in range(2, 65):
        undefeated = n
        for _ in range(swiss_rounds(n)):
            undefeated = (undefeated + 1) // 2  # half win; an odd one out gets a bye (a win)
        assert undefeated == 1, n
