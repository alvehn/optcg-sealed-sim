"""A rule-of-thumb bot: develop the board, push damage, defend when life is low.

It is deliberately simple. It is the workhorse for bulk simulation, and its card ratings
should later be checked against a search-based agent (ISMCTS).
"""

from __future__ import annotations

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
from optcg.engine.game import can_attack, power
from optcg.engine.state import CardInstance, GameState, Phase


class HeuristicAgent:
    name = "heuristic"

    def __init__(self, defend_at_life: int = 2, protect_cost: int = 4):
        self.defend_at_life = defend_at_life  # start blocking/countering leader hits here
        self.protect_cost = protect_cost  # counter to save Characters this expensive

    def choose(self, s: GameState, actions: list[Action]) -> Action:
        if s.phase == Phase.MULLIGAN:
            return self._mulligan(s)
        if s.phase == Phase.MAIN:
            return self._main(s, actions)
        if s.phase == Phase.BLOCK:
            return self._block(s, actions)
        if s.phase == Phase.COUNTER:
            return self._counter(s, actions)
        return actions[0]

    # --- turn player ----------------------------------------------------------------

    def _mulligan(self, s: GameState) -> Action:
        hand = s.players[s.decider].hand
        early = sum(1 for c in hand if c.card.category == "Character" and (c.card.cost or 0) <= 4)
        return Mulligan(redraw=early < 2)

    def _main(self, s: GameState, actions: list[Action]) -> Action:
        p = s.players[s.active]
        opp = s.players[1 - s.active]

        # 1. Play the most expensive Character we can afford. When the board is full,
        #    only replace a Character that costs at least 2 less.
        plays = [a for a in actions if isinstance(a, PlayCard)]
        if plays:

            def value(a: PlayCard) -> int:
                gain = s.find(a.uid).card.cost or 0
                if a.replace_uid is not None:
                    gain -= (s.find(a.replace_uid).card.cost or 0) + 2
                return gain

            best = max(plays, key=value)
            if best.replace_uid is None or value(best) >= 0:
                return best

        # 2. Attach DON!!: bring an attacker up to the opponent leader's power, otherwise
        #    stack the rest on the leader.
        if p.don_active:
            ready = [c for c in p.field_cards() if can_attack(s, c)]
            need = power(s, opp.leader)
            short = [
                c for c in ready if power(s, c) < need and need - power(s, c) <= 1000 * p.don_active
            ]
            if short:
                target = min(short, key=lambda c: need - power(s, c))
                return AttachDon(target.uid)
            if can_attack(s, p.leader) or not ready:
                return AttachDon(p.leader.uid)
            return AttachDon(ready[0].uid)

        # 3. Attack: K.O. rested Characters worth 3+ cost, otherwise hit the leader.
        attacks = [a for a in actions if isinstance(a, Attack)]
        if attacks:
            best = max(attacks, key=lambda a: self._attack_score(s, a))
            if self._attack_score(s, best) > 0:
                return best

        return EndTurn()

    def _attack_score(self, s: GameState, a: Attack) -> float:
        attacker, target = s.find(a.attacker_uid), s.find(a.target_uid)
        surplus = power(s, attacker) - power(s, target)
        if surplus < 0:
            return 0
        opp = s.players[target.owner]
        if target is opp.leader:
            score = 10 + (5 if attacker.card.has("Double Attack") else 0)
            if not opp.life:
                score += 100  # lethal
        else:
            score = 3 * (target.card.cost or 0)
        # Prefer the attack that leaves the defender needing the most counter.
        return score + surplus / 1000

    # --- defending player -------------------------------------------------------------

    def _threat(self, s: GameState) -> tuple[CardInstance, CardInstance, int]:
        b = s.battle
        attacker, target = s.find(b.attacker_uid), s.find(b.target_uid)
        return attacker, target, power(s, attacker) - power(s, target)

    def _block(self, s: GameState, actions: list[Action]) -> Action:
        d = s.players[s.decider]
        attacker, target, surplus = self._threat(s)
        blockers = [s.find(a.blocker_uid) for a in actions if a.blocker_uid is not None]
        if surplus < 0 or not blockers:
            return Block(None)
        lethal = target is d.leader and (not d.life or attacker.card.has("Double Attack"))
        low_life = target is d.leader and len(d.life) <= self.defend_at_life
        saving = target is not d.leader and (target.card.cost or 0) >= self.protect_cost
        if lethal or low_life or saving:
            cheapest = min(blockers, key=lambda c: c.card.cost or 0)
            if target is d.leader or (cheapest.card.cost or 0) < (target.card.cost or 0):
                return Block(cheapest.uid)
        return Block(None)

    def _counter(self, s: GameState, actions: list[Action]) -> Action:
        d = s.players[s.decider]
        _, target, surplus = self._threat(s)
        counters = [s.find(a.uid) for a in actions if isinstance(a, PlayCounter)]
        if surplus < 0 or not counters:
            return PassCounter()
        needed = surplus + 1000  # defender must end strictly above the attacker
        available = sum(c.card.counter for c in counters)
        if available < needed:
            return PassCounter()
        if target is d.leader:
            worth_it = len(d.life) <= self.defend_at_life
        else:
            worth_it = (target.card.cost or 0) >= self.protect_cost and needed <= 2000
        if not worth_it:
            return PassCounter()
        # Smallest single card that covers it, else the biggest one and keep going.
        enough = [c for c in counters if c.card.counter >= needed]
        pick = (
            min(enough, key=lambda c: c.card.counter)
            if enough
            else max(counters, key=lambda c: c.card.counter)
        )
        return PlayCounter(pick.uid)
