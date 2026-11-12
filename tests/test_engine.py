from conftest import char, leader

from optcg.agents import HeuristicAgent, RandomAgent
from optcg.engine import Phase, apply, legal_actions, new_game
from optcg.engine.actions import (
    AttachDon,
    Attack,
    Block,
    EndTurn,
    Mulligan,
    PassCounter,
    PlayCard,
    PlayCounter,
)
from optcg.sim import play_game


def start(deck, seed=1, life=5):
    s = new_game((leader(life), leader(life)), (list(deck), list(deck)), seed=seed, first=0)
    apply(s, Mulligan(False))
    apply(s, Mulligan(False))
    return s


def to_turn(s, n):
    while s.turn < n:
        apply(s, EndTurn())


def test_setup(vanilla_deck):
    s = start(vanilla_deck)
    p0, p1 = s.players
    assert (s.turn, s.active, s.phase) == (1, 0, Phase.MAIN)
    assert len(p0.hand) == 5  # first player does not draw on turn 1
    assert len(p0.life) == 5 and len(p1.life) == 5
    assert p0.don_active == 1  # first player gets 1 DON!! on turn 1
    assert len(p0.deck) == 40 - 5 - 5


def test_second_player_draws_and_gets_two_don(vanilla_deck):
    s = start(vanilla_deck)
    to_turn(s, 2)
    p1 = s.players[1]
    assert len(p1.hand) == 6 and p1.don_active == 2


def test_no_attacks_on_own_first_turn(vanilla_deck):
    s = start(vanilla_deck)
    assert not any(isinstance(a, Attack) for a in legal_actions(s))
    to_turn(s, 2)
    assert not any(isinstance(a, Attack) for a in legal_actions(s))
    to_turn(s, 3)
    assert any(isinstance(a, Attack) for a in legal_actions(s))


def test_don_returns_and_accumulates(vanilla_deck):
    s = start(vanilla_deck)
    apply(s, AttachDon(s.players[0].leader.uid))
    to_turn(s, 3)
    p0 = s.players[0]
    assert p0.leader.don == 0
    assert p0.don_active == 3  # 1 from turn 1, +2 on turn 3


def test_mulligan_redraws_five(vanilla_deck):
    s = new_game((leader(), leader()), (vanilla_deck, vanilla_deck), seed=3, first=0)
    apply(s, Mulligan(True))
    assert len(s.players[0].hand) == 5
    assert s.decider == 1
    assert len(s.players[0].deck) + len(s.players[0].hand) == 40


def test_attack_leader_takes_life_into_hand(vanilla_deck):
    s = start(vanilla_deck)
    to_turn(s, 3)
    p0, p1 = s.players
    hand_before = len(p1.hand)
    apply(s, Attack(p0.leader.uid, p1.leader.uid))  # 5000 vs 5000: attacker wins ties
    assert s.phase == Phase.COUNTER and s.decider == 1
    apply(s, PassCounter())
    assert len(p1.life) == 4 and len(p1.hand) == hand_before + 1
    assert s.phase == Phase.MAIN and s.decider == 0
    assert p0.leader.rested


def test_counter_stops_attack(vanilla_deck):
    s = start(vanilla_deck)
    to_turn(s, 3)
    p0, p1 = s.players
    apply(s, Attack(p0.leader.uid, p1.leader.uid))
    counter = next(c for c in p1.hand if c.card.counter)
    apply(s, PlayCounter(counter.uid))
    apply(s, PassCounter())
    assert len(p1.life) == 5
    assert counter in p1.trash


def test_attached_don_only_counts_on_owners_turn(vanilla_deck):
    s = start(vanilla_deck)
    to_turn(s, 3)
    p0, p1 = s.players
    apply(s, AttachDon(p0.leader.uid))
    apply(s, Attack(p0.leader.uid, p1.leader.uid))  # 6000 vs 5000
    apply(s, PlayCounter(next(c for c in p1.hand if c.card.counter).uid))  # 5000 + 1000 = 6000
    apply(s, PassCounter())
    assert len(p1.life) == 4  # tie goes to the attacker


def test_blocker_redirects_and_is_ko(vanilla_deck):
    s = start(vanilla_deck)
    p1 = s.players[1]
    blocker = new_card(s, 1, char(1, 1000, keywords=("Blocker",)))
    p1.characters.append(blocker)
    to_turn(s, 3)
    p0 = s.players[0]
    apply(s, Attack(p0.leader.uid, p1.leader.uid))
    assert s.phase == Phase.BLOCK
    apply(s, Block(blocker.uid))
    apply(s, PassCounter())
    assert blocker in p1.trash and len(p1.life) == 5


def test_characters_have_summoning_sickness_unless_rush(vanilla_deck):
    s = start(vanilla_deck)
    to_turn(s, 3)
    p0 = s.players[0]
    normal = new_card(s, 0, char(1, 2000))
    rusher = new_card(s, 0, char(1, 2000, keywords=("Rush",)))
    p0.hand += [normal, rusher]
    apply(s, PlayCard(normal.uid))
    apply(s, PlayCard(rusher.uid))
    attackers = {a.attacker_uid for a in legal_actions(s) if isinstance(a, Attack)}
    assert rusher.uid in attackers and normal.uid not in attackers


def test_full_board_requires_replacement(vanilla_deck):
    s = start(vanilla_deck)
    p0 = s.players[0]
    p0.characters += [new_card(s, 0, char(1, 2000)) for _ in range(5)]
    extra = new_card(s, 0, char(1, 2000))
    p0.hand.append(extra)
    plays = [a for a in legal_actions(s) if isinstance(a, PlayCard) and a.uid == extra.uid]
    assert len(plays) == 5 and all(a.replace_uid is not None for a in plays)


def test_zero_life_hit_loses(vanilla_deck):
    s = start(vanilla_deck, life=1)
    to_turn(s, 3)
    p0, p1 = s.players
    apply(s, Attack(p0.leader.uid, p1.leader.uid))
    apply(s, PassCounter())
    assert len(p1.life) == 0 and s.phase == Phase.MAIN
    p0.leader.rested = False  # pretend a second attacker
    apply(s, Attack(p0.leader.uid, p1.leader.uid))
    apply(s, PassCounter())
    assert s.phase == Phase.GAME_OVER and s.winner == 0


def test_double_attack_and_banish(vanilla_deck):
    s = start(vanilla_deck)
    to_turn(s, 3)
    p0, p1 = s.players
    da = new_card(s, 0, char(1, 6000, keywords=("Double Attack", "Banish")))
    da.played_turn = 0
    p0.characters.append(da)
    hand_before = len(p1.hand)
    apply(s, Attack(da.uid, p1.leader.uid))
    apply(s, PassCounter())
    assert len(p1.life) == 3 and len(p1.trash) == 2 and len(p1.hand) == hand_before


def test_full_games_terminate(vanilla_deck):
    for seed in range(30):
        for agents in (
            (RandomAgent(seed), RandomAgent(seed + 1)),
            (HeuristicAgent(), RandomAgent()),
        ):
            s = new_game((leader(), leader()), (vanilla_deck, vanilla_deck), seed=seed)
            r = play_game(s, agents)
            assert s.phase == Phase.GAME_OVER
            assert r.winner in (0, 1, None)


def test_heuristic_beats_random(vanilla_deck):
    wins = 0
    for seed in range(40):
        s = new_game((leader(), leader()), (vanilla_deck, vanilla_deck), seed=seed, first=seed % 2)
        wins += play_game(s, (HeuristicAgent(), RandomAgent(seed))).winner == 0
    assert wins >= 32


def new_card(s, owner, card):
    return s.new_instance(card, owner)
