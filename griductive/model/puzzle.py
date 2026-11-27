"""Public puzzle state exposed to the logic agent and full puzzle structure."""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from griductive.model.cell import CellId, Character, Status
from griductive.model.clue import Clue


@dataclass(frozen=True)
class Puzzle:
    """Full puzzle description held only by GameEngine."""

    n: int
    characters: Mapping[CellId, Character]
    solution: Mapping[CellId, Status]
    clues: Mapping[CellId, Clue]
    initial_revealed: frozenset[CellId]
    human_clues: Mapping[CellId, str] = field(
        default_factory=lambda: MappingProxyType({})
    )


@dataclass(frozen=True)
class PublicState:
    """Information currently visible to the logic agent."""

    n: int
    revealed_clues: tuple[Clue, ...]
    proved: Mapping[CellId, Status]
    unsolved: tuple[CellId, ...]
