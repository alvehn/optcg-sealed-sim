from __future__ import annotations

from typing import Protocol

from optcg.engine.actions import Action
from optcg.engine.state import GameState


class Agent(Protocol):
    name: str

    def choose(self, s: GameState, actions: list[Action]) -> Action:
        """Pick one of `actions` for player `s.decider`. Must not mutate `s`."""
        ...
