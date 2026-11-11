"""GameEngine core class executing the Griductive gameplay logic."""

from __future__ import annotations

from typing import Callable, Mapping

from griductive.engine.dummy_engine import VerdictOutcome, VerdictResult
from griductive.model.cell import CellId, Status
from griductive.model.clue import Clue
from griductive.model.puzzle import PublicState, Puzzle


# Oracle callback type: (state, cell) -> Classification or duck-typed object with .verdict
Oracle = Callable[[PublicState, CellId], any]


class GameEngine:
    """Game engine managing state and validating verdicts via deduction oracle."""

    def __init__(self, puzzle: Puzzle, oracle: Oracle | None = None) -> None:
        self.puzzle = puzzle
        self.oracle = oracle
        self._proved: dict[CellId, Status] = {}
        self._revealed_clues: list[Clue] = []
        self.restart()

    @property
    def n(self) -> int:
        return self.puzzle.n

    def public_state(self) -> PublicState:
        """Return the current public state visible to logic agent and GUI."""
        n = self.n
        unsolved = tuple(
            CellId(r, c)
            for r in range(n)
            for c in range(n)
            if CellId(r, c) not in self._proved
        )
        return PublicState(
            n=n,
            revealed_clues=tuple(self._revealed_clues),
            proved=dict(self._proved),
            unsolved=unsolved,
        )

    def submit(self, cell: CellId, status: Status) -> VerdictResult:
        """Submit a status verdict for a cell using oracle (or ground truth fallback)."""
        if cell in self._proved:
            return VerdictResult(
                outcome=VerdictOutcome.ACCEPTED,
                cell=cell,
                revealed_clue=self.puzzle.clues.get(cell),
            )

        if self.oracle is not None:
            classification = self.oracle(self.public_state(), cell)
            verdict_name = (
                classification.verdict.name
                if hasattr(classification.verdict, "name")
                else str(classification.verdict)
            )
            queries = getattr(classification, "queries", ())

            if verdict_name == "INCONSISTENT":
                return VerdictResult(VerdictOutcome.INCONSISTENT, cell, None, queries)
            if verdict_name == "UNKNOWN":
                return VerdictResult(VerdictOutcome.NOT_PROVABLE, cell, None, queries)

            if verdict_name == status.name:
                self._proved[cell] = status
                clue = self.puzzle.clues[cell]
                if clue not in self._revealed_clues:
                    self._revealed_clues.append(clue)
                return VerdictResult(VerdictOutcome.ACCEPTED, cell, clue, queries)
            else:
                return VerdictResult(VerdictOutcome.CONTRADICTED, cell, None, queries)

        # Fallback without oracle: check against puzzle solution directly
        expected_status = self.puzzle.solution[cell]
        if status is expected_status:
            self._proved[cell] = status
            clue = self.puzzle.clues[cell]
            if clue not in self._revealed_clues:
                self._revealed_clues.append(clue)
            return VerdictResult(VerdictOutcome.ACCEPTED, cell, clue)
        else:
            return VerdictResult(VerdictOutcome.CONTRADICTED, cell, None)

    def is_solved(self) -> bool:
        """Return True if all cells in the grid are solved."""
        return len(self._proved) == self.n * self.n

    def restart(self) -> None:
        """Reset game state to initial revealed cards."""
        self._proved = {}
        self._revealed_clues = []
        for cell in sorted(self.puzzle.initial_revealed):
            self._proved[cell] = self.puzzle.solution[cell]
            clue = self.puzzle.clues.get(cell)
            if clue and clue not in self._revealed_clues:
                self._revealed_clues.append(clue)
