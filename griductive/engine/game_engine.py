"""Game engine that accepts verdicts only when confirmed by a logic oracle."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Protocol

from griductive.model.cell import CellId, Status
from griductive.model.clue import Clue
from griductive.model.puzzle import PublicState, Puzzle


class VerdictOutcome(Enum):
    """Outcome of submitting a proposed cell status."""

    ACCEPTED = "ACCEPTED"
    NOT_PROVABLE = "NOT_PROVABLE"
    CONTRADICTED = "CONTRADICTED"
    INCONSISTENT = "INCONSISTENT"


@dataclass(frozen=True)
class VerdictResult:
    """Outcome and newly revealed information from one submission."""

    outcome: VerdictOutcome
    cell: CellId
    revealed_clue: Clue | None = None
    queries: tuple[object, ...] = ()


class Classification(Protocol):
    """Minimal result interface required from the deduction oracle."""

    @property
    def verdict(self) -> object:
        """Return the classified verdict."""

    @property
    def queries(self) -> tuple[object, ...]:
        """Return the solver queries supporting the classification."""


Oracle = Callable[[PublicState, CellId], Classification]


class GameEngine:
    """Manage visible game state and delegate verdicts to an oracle."""

    def __init__(self, puzzle: Puzzle, oracle: Oracle) -> None:
        """Create an engine for ``puzzle`` using the supplied oracle.

        Args:
            puzzle: Complete puzzle data, including hidden information.
            oracle: Classifies cells using only the supplied public state.
        """
        self.puzzle = puzzle
        self.oracle = oracle
        self._proved: dict[CellId, Status] = {}
        self._revealed_clues: list[Clue] = []
        self.restart()

    @property
    def n(self) -> int:
        """Return the width and height of the puzzle grid."""
        return self.puzzle.n

    def public_state(self) -> PublicState:
        """Return an immutable view containing only revealed information."""
        unsolved = tuple(
            CellId(row, col)
            for row in range(self.n)
            for col in range(self.n)
            if CellId(row, col) not in self._proved
        )
        return PublicState(
            n=self.n,
            revealed_clues=tuple(self._revealed_clues),
            proved=MappingProxyType(dict(sorted(self._proved.items()))),
            unsolved=unsolved,
        )

    def submit(self, cell: CellId, status: Status) -> VerdictResult:
        """Submit a proposed status and reveal its clue only if proved.

        Raises:
            ValueError: If the cell is not in the puzzle or has already been
                solved, or if ``status`` is not a ``Status``.
            TypeError: If the oracle result does not provide a verdict.
            ValueError: If the oracle returns an unsupported verdict.
        """
        if cell not in self.puzzle.characters:
            raise ValueError(f"cell {cell} is not part of this puzzle")
        if cell in self._proved:
            raise ValueError(f"cell {cell} has already been solved")
        if not isinstance(status, Status):
            raise ValueError("status must be a Status")

        classification = self.oracle(self.public_state(), cell)
        if not hasattr(classification, "verdict"):
            raise TypeError("oracle result must provide a verdict")
        verdict = classification.verdict
        verdict_name = getattr(verdict, "name", None)
        if verdict_name is None:
            verdict_name = getattr(verdict, "value", verdict)
        verdict_name = str(verdict_name)
        queries = tuple(getattr(classification, "queries", ()))

        if verdict_name == "INCONSISTENT":
            return VerdictResult(VerdictOutcome.INCONSISTENT, cell, None, queries)
        if verdict_name == "UNKNOWN":
            return VerdictResult(VerdictOutcome.NOT_PROVABLE, cell, None, queries)
        if verdict_name not in (Status.CRIMINAL.name, Status.INNOCENT.name):
            raise ValueError(f"oracle returned unsupported verdict: {verdict_name!r}")

        if verdict_name != status.name:
            return VerdictResult(VerdictOutcome.CONTRADICTED, cell, None, queries)

        clue = self.puzzle.clues[cell]
        self._proved[cell] = status
        self._revealed_clues.append(clue)
        return VerdictResult(VerdictOutcome.ACCEPTED, cell, clue, queries)

    def is_solved(self) -> bool:
        """Return whether every cell has a proved status."""
        return len(self._proved) == self.n * self.n

    def restart(self) -> None:
        """Reset the game to the puzzle's initially revealed cards."""
        self._proved = {
            cell: self.puzzle.solution[cell]
            for cell in sorted(self.puzzle.initial_revealed)
        }
        self._revealed_clues = [
            self.puzzle.clues[cell] for cell in sorted(self.puzzle.initial_revealed)
        ]

    @classmethod
    def load(cls, path: str, oracle: Oracle) -> "GameEngine":
        """Load a puzzle file and construct an engine for it.

        Args:
            path: JSON puzzle path.
            oracle: Deduction callback used to classify submissions.

        Returns:
            A game engine initialized to the puzzle's starting state.

        Raises:
            PuzzleError: If the puzzle file is malformed or invalid.
        """
        from griductive.io.loader import load_puzzle

        return cls(load_puzzle(path), oracle)
