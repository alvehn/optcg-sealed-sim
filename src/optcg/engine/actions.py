"""Actions a player can take. The engine lists the legal ones at every decision point."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Mulligan:
    redraw: bool


@dataclass(frozen=True)
class PlayCard:
    uid: int
    # With 5 Characters already on the field, one must be trashed to make room.
    replace_uid: int | None = None


@dataclass(frozen=True)
class AttachDon:
    target_uid: int


@dataclass(frozen=True)
class Attack:
    attacker_uid: int
    target_uid: int


@dataclass(frozen=True)
class EndTurn:
    pass


@dataclass(frozen=True)
class Block:
    blocker_uid: int | None  # None = don't block


@dataclass(frozen=True)
class PlayCounter:
    uid: int


@dataclass(frozen=True)
class PassCounter:
    pass


Action = Mulligan | PlayCard | AttachDon | Attack | EndTurn | Block | PlayCounter | PassCounter
