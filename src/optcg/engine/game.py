"""Rules engine: setup, legal actions and action resolution.

This is the "vanilla" engine: it handles the turn structure, DON!!, attacks, blocking,
counters, life and the keywords Blocker / Rush / Double Attack / Banish. Card effect text
(On Play, When Attacking, Triggers, Events, Stages) is not executed yet; that comes with
the effect DSL.

The engine is a state machine: `legal_actions(state)` lists what `state.decider` may do,
and `apply(state, action)` advances the game. Agents never mutate state directly.
"""

from __future__ import annotations

import copy
import random

from optcg.cards import CardDef
from optcg.engine.actions import (
    Action,
    AttachDon,
    Attack,
    Block,
    EndTurn,
    Mulligan,
    PassCounter,
    PlayCard,
    PlayCounter,
)
from optcg.engine.state import (
    MAX_CHARACTERS,
    STARTING_HAND,
    Battle,
    CardInstance,
    GameState,
    Phase,
    PlayerState,
)

# --- setup ------------------------------------------------------------------------------


def new_game(
    leaders: tuple[CardDef, CardDef],
    decks: tuple[list[CardDef], list[CardDef]],
    seed: int | None = None,
    first: int | None = None,
    max_turns: int = 60,
    log: bool = False,
) -> GameState:
    rng = random.Random(seed)
    s = GameState(players=[], first=0, rng=rng, max_turns=max_turns)
    for i in (0, 1):
        leader = s.new_instance(leaders[i], owner=i)
        deck = [s.new_instance(c, owner=i) for c in decks[i]]
        rng.shuffle(deck)
        s.players.append(PlayerState(leader=leader, deck=deck))
    s.first = rng.randrange(2) if first is None else first
    s.log = [] if log else None
    for p in s.players:
        _draw(p, STARTING_HAND)
    s.active = s.decider = s.first
    s.phase = Phase.MULLIGAN
    return s


def clone(s: GameState) -> GameState:
    return copy.deepcopy(s)


# --- queries ----------------------------------------------------------------------------


def power(s: GameState, c: CardInstance) -> int:
    """Current power, including attached DON!! (owner's turn only) and battle counters."""
    p = c.card.power or 0
    if c.owner == s.active:
        p += 1000 * c.don
    if s.battle and s.battle.target_uid == c.uid:
        p += s.battle.counter_power
    return p


def can_attack(s: GameState, c: CardInstance) -> bool:
    if c.rested or s.players[c.owner].turns_taken == 0:
        return False  # neither player may attack on their own first turn
    is_leader = c is s.players[c.owner].leader
    return is_leader or c.played_turn != s.turn or c.card.has("Rush")


def legal_actions(s: GameState) -> list[Action]:
    if s.phase == Phase.MULLIGAN:
        return [Mulligan(False), Mulligan(True)]
    if s.phase == Phase.MAIN:
        return _main_actions(s)
    if s.phase == Phase.BLOCK:
        d = s.players[s.decider]
        return [Block(None)] + [
            Block(c.uid) for c in d.characters if c.card.has("Blocker") and not c.rested
        ]
    if s.phase == Phase.COUNTER:
        d = s.players[s.decider]
        return [PassCounter()] + [PlayCounter(c.uid) for c in d.hand if c.card.counter]
    return []


def _main_actions(s: GameState) -> list[Action]:
    p = s.players[s.active]
    opp = s.players[1 - s.active]
    actions: list[Action] = []
    for c in p.hand:
        # Only Characters are playable until the effect DSL can resolve Events and Stages.
        if c.card.category != "Character" or (c.card.cost or 0) > p.don_active:
            continue
        if len(p.characters) < MAX_CHARACTERS:
            actions.append(PlayCard(c.uid))
        else:
            actions.extend(PlayCard(c.uid, r.uid) for r in p.characters)
    if p.don_active:
        actions.extend(AttachDon(c.uid) for c in p.field_cards())
    targets = [opp.leader] + [c for c in opp.characters if c.rested]
    for a in p.field_cards():
        if can_attack(s, a):
            actions.extend(Attack(a.uid, t.uid) for t in targets)
    actions.append(EndTurn())
    return actions


# --- transitions ------------------------------------------------------------------------


def apply(s: GameState, action: Action) -> None:
    if s.phase == Phase.GAME_OVER:
        raise ValueError("game is over")
    if action not in legal_actions(s):
        raise ValueError(f"illegal action {action} in phase {s.phase.name}")

    match action:
        case Mulligan(redraw):
            _mulligan(s, redraw)
        case PlayCard(uid, replace_uid):
            _play_card(s, uid, replace_uid)
        case AttachDon(target_uid):
            p = s.players[s.active]
            p.don_active -= 1
            s.find(target_uid).don += 1
        case Attack(attacker_uid, target_uid):
            _declare_attack(s, attacker_uid, target_uid)
        case Block(blocker_uid):
            if blocker_uid is not None:
                blocker = s.find(blocker_uid)
                blocker.rested = True
                s.battle.target_uid = blocker_uid
                s.note(f"blocks with {blocker.card.name}", s.decider)
            s.phase = Phase.COUNTER
        case PlayCounter(uid):
            d = s.players[s.decider]
            c = s.find(uid)
            d.hand.remove(c)
            d.trash.append(c)
            s.battle.counter_power += c.card.counter
            s.note(f"counters +{c.card.counter} with {c.card.name}", s.decider)
        case PassCounter():
            _resolve_battle(s)
        case EndTurn():
            _end_turn(s)


def _mulligan(s: GameState, redraw: bool) -> None:
    p = s.players[s.decider]
    if redraw:
        p.deck.extend(p.hand)
        p.hand.clear()
        s.rng.shuffle(p.deck)
        _draw(p, STARTING_HAND)
    p.mulliganed = True
    if s.decider == s.first:
        s.decider = 1 - s.first
        return
    # Both players have decided: place life cards, then start the first turn.
    for pl in s.players:
        for _ in range(pl.leader.card.life or 5):
            pl.life.append(pl.deck.pop())
    _start_turn(s)


def _play_card(s: GameState, uid: int, replace_uid: int | None) -> None:
    p = s.players[s.active]
    c = s.find(uid)
    if replace_uid is not None:
        _trash_from_field(s, s.find(replace_uid))
    p.hand.remove(c)
    p.don_active -= c.card.cost or 0
    p.don_rested += c.card.cost or 0
    c.played_turn = s.turn
    p.characters.append(c)
    s.note(f"plays {c.card.name} ({c.card.cost})")


def _declare_attack(s: GameState, attacker_uid: int, target_uid: int) -> None:
    attacker = s.find(attacker_uid)
    attacker.rested = True
    s.battle = Battle(attacker_uid, target_uid)
    s.decider = 1 - s.active
    d = s.players[s.decider]
    s.note(f"{attacker.card.name} ({power(s, attacker)}) attacks {s.find(target_uid).card.name}")
    has_blocker = any(c.card.has("Blocker") and not c.rested for c in d.characters)
    s.phase = Phase.BLOCK if has_blocker else Phase.COUNTER


def _resolve_battle(s: GameState) -> None:
    b = s.battle
    attacker, target = s.find(b.attacker_uid), s.find(b.target_uid)
    defender = s.players[target.owner]
    if power(s, attacker) >= power(s, target):
        if target is defender.leader:
            hits = 2 if attacker.card.has("Double Attack") else 1
            for _ in range(hits):
                if not defender.life:
                    _finish(s, winner=attacker.owner)
                    return
                life_card = defender.life.pop()
                if attacker.card.has("Banish"):
                    defender.trash.append(life_card)
                else:
                    defender.hand.append(life_card)  # TODO: [Trigger] choice
            s.note(f"hits leader, {len(defender.life)} life left")
        else:
            _trash_from_field(s, target)
            s.note(f"K.O.s {target.card.name}")
    s.battle = None
    s.phase = Phase.MAIN
    s.decider = s.active


def _trash_from_field(s: GameState, c: CardInstance) -> None:
    owner = s.players[c.owner]
    owner.characters.remove(c)
    owner.don_rested += c.don  # attached DON!! returns to the cost area rested
    c.don = 0
    c.rested = False
    owner.trash.append(c)


def _end_turn(s: GameState) -> None:
    s.players[s.active].turns_taken += 1
    s.note("ends turn")
    if s.turn >= s.max_turns:
        _finish(s, winner=None)
        return
    s.active = 1 - s.active
    _start_turn(s)


def _start_turn(s: GameState) -> None:
    s.turn += 1
    p = s.players[s.active]
    # Refresh phase: return attached DON!!, set everything active.
    for c in p.field_cards():
        p.don_active += c.don
        c.don = 0
        c.rested = False
    p.don_active += p.don_rested
    p.don_rested = 0
    # Draw phase: the first player skips their first draw.
    going_first_turn_one = s.active == s.first and p.turns_taken == 0
    if not going_first_turn_one:
        if not p.deck:
            _finish(s, winner=1 - s.active)
            return
        _draw(p, 1)
    # DON!! phase: +2, or +1 on the first player's first turn.
    added = min(1 if going_first_turn_one else 2, p.don_deck)
    p.don_deck -= added
    p.don_active += added
    s.phase = Phase.MAIN
    s.decider = s.active
    # A player whose deck is empty loses (rule processing).
    if not p.deck:
        _finish(s, winner=1 - s.active)


def _draw(p: PlayerState, n: int) -> None:
    for _ in range(min(n, len(p.deck))):
        p.hand.append(p.deck.pop())


def _finish(s: GameState, winner: int | None) -> None:
    s.winner = winner
    s.phase = Phase.GAME_OVER
    s.battle = None
    s.note(f"game over, winner={winner}")
