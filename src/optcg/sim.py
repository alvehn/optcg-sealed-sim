"""Run games between agents."""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from optcg.agents.base import Agent
from optcg.cards import CardDef
from optcg.engine import Phase, apply, legal_actions, new_game
from optcg.engine.state import GameState

MAX_DECISIONS = 20_000  # guard against an agent that never ends its turn


@dataclass
class GameResult:
    winner: int | None
    first: int
    turns: int
    seed: int


def play_game(s: GameState, agents: tuple[Agent, Agent], seed: int = 0) -> GameResult:
    for _ in range(MAX_DECISIONS):
        if s.phase == Phase.GAME_OVER:
            break
        actions = legal_actions(s)
        apply(s, agents[s.decider].choose(s, actions))
    else:
        raise RuntimeError("game did not finish; an agent may be looping")
    return GameResult(winner=s.winner, first=s.first, turns=s.turn, seed=seed)


def random_deck(pool: list[CardDef], rng: random.Random, size: int = 40) -> list[CardDef]:
    """Placeholder until the pack sampler + deckbuilder exist: `size` random non-leader cards.

    Sealed has no 4-copy limit, so sampling with replacement is legal.
    """
    candidates = [c for c in pool if c.category != "Leader"]
    return [rng.choice(candidates) for _ in range(size)]


def run_match(
    make_agents: Callable[[int], tuple[Agent, Agent]],
    leaders: tuple[CardDef, CardDef],
    decks: tuple[list[CardDef], list[CardDef]],
    games: int,
    seed: int = 0,
) -> list[GameResult]:
    """Play `games` games, alternating who goes first so neither side gets the edge."""
    results = []
    for g in range(games):
        game_seed = seed + g
        s = new_game(leaders, decks, seed=game_seed, first=g % 2)
        results.append(play_game(s, make_agents(game_seed), seed=game_seed))
    return results
