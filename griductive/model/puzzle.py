"""Public puzzle state exposed to the logic agent."""

from dataclasses import dataclass
from typing import Mapping

from griductive.model.cell import CellId, Status
from griductive.model.clue import Clue


@dataclass(frozen=True)
class PublicState:
    """Information currently visible to the logic agent."""

    n: int
    revealed_clues: tuple[Clue, ...]
    proved: Mapping[CellId, Status]
    unsolved: tuple[CellId, ...]
