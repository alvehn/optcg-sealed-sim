"""Mutable game state. Kept as plain dataclasses so it can be deep-copied for search."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto

from optcg.cards import CardDef

DON_DECK_SIZE = 10
STARTING_HAND = 5
MAX_CHARACTERS = 5


class Phase(Enum):
    MULLIGAN = auto()
    MAIN = auto()
    BLOCK = auto()  # defender chooses whether to block
    COUNTER = auto()  # defender plays counters
    GAME_OVER = auto()


@dataclass
class CardInstance:
    uid: int
    card: CardDef
    owner: int
    rested: bool = False
    don: int = 0  # DON!! cards attached
    played_turn: int = -1


@dataclass
class PlayerState:
    leader: CardInstance
    deck: list[CardInstance]  # deck[-1] is the top card
    hand: list[CardInstance] = field(default_factory=list)
    life: list[CardInstance] = field(default_factory=list)  # life[-1] is the top card
    trash: list[CardInstance] = field(default_factory=list)
    characters: list[CardInstance] = field(default_factory=list)
    don_deck: int = DON_DECK_SIZE
    don_active: int = 0
    don_rested: int = 0
    turns_taken: int = 0
    mulliganed: bool = False

    def field_cards(self) -> list[CardInstance]:
        return [self.leader, *self.characters]


@dataclass
class Battle:
    attacker_uid: int
    target_uid: int
    counter_power: int = 0  # power added to the defending card this battle


@dataclass
class GameState:
    players: list[PlayerState]
    first: int  # player who goes first
    rng: random.Random
    active: int = 0  # whose turn it is
    turn: int = 0  # global turn number, 1 = first player's first turn
    phase: Phase = Phase.MULLIGAN
    decider: int = 0  # who must choose the next action
    battle: Battle | None = None
    winner: int | None = None  # None at game end = draw (turn limit)
    max_turns: int = 60
    log: list[str] | None = None  # set to [] to record a game log
    next_uid: int = 1

    def new_instance(self, card: CardDef, owner: int) -> CardInstance:
        c = CardInstance(self.next_uid, card, owner=owner)
        self.next_uid += 1
        return c

    def find(self, uid: int) -> CardInstance:
        for p in self.players:
            for c in p.field_cards():
                if c.uid == uid:
                    return c
            for c in p.hand:
                if c.uid == uid:
                    return c
        raise KeyError(uid)

    def note(self, msg: str, player: int | None = None) -> None:
        if self.log is not None:
            who = self.active if player is None else player
            self.log.append(f"T{self.turn} P{who}: {msg}")
