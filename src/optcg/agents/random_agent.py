from __future__ import annotations

import random

from optcg.engine.actions import Action
from optcg.engine.state import GameState


class RandomAgent:
    """Uniformly random legal moves. Used for smoke tests and as a floor baseline."""

    name = "random"

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)

    def choose(self, s: GameState, actions: list[Action]) -> Action:
        return self.rng.choice(actions)
