"""Fixed dummy engine for GUI testing and standalone execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from griductive.model.cell import CellId, Character, Status
from griductive.model.clue import Clue, Fact
from griductive.model.puzzle import PublicState, Puzzle


class VerdictOutcome(Enum):
    """Outcome of submitting a status verdict to the game engine."""

    ACCEPTED = "ACCEPTED"
    NOT_PROVABLE = "NOT_PROVABLE"
    CONTRADICTED = "CONTRADICTED"
    INCONSISTENT = "INCONSISTENT"


@dataclass(frozen=True)
class VerdictResult:
    """Result returned by game engine submit call."""

    outcome: VerdictOutcome
    cell: CellId
    revealed_clue: Clue | None = None
    queries: tuple = ()


class DummyEngine:
    """Fixed 3x3 dummy engine for GUI development and testing."""

    def __init__(self, puzzle: Puzzle | None = None) -> None:
        if puzzle is None:
            puzzle = self.create_default_puzzle()
        self.puzzle = puzzle
        self._proved: dict[CellId, Status] = {}
        self._revealed_clues: list[Clue] = []
        self.restart()

    @staticmethod
    def create_default_puzzle() -> Puzzle:
        """Create a default 3x3 puzzle with 9 characters and clues."""
        n = 3
        characters: dict[CellId, Character] = {}
        solution: dict[CellId, Status] = {}
        clues: dict[CellId, Clue] = {}

        names_jobs = [
            ("Alice", "Detective"),
            ("Bob", "Doctor"),
            ("Charlie", "Artist"),
            ("Diana", "Chef"),
            ("Edward", "Engineer"),
            ("Fiona", "Lawyer"),
            ("George", "Teacher"),
            ("Hannah", "Pilot"),
            ("Ian", "Writer"),
        ]

        # Define 3x3 grid status solution pattern
        # Row 0: A1=CRIMINAL, B1=INNOCENT, C1=CRIMINAL
        # Row 1: A2=INNOCENT, B2=CRIMINAL, C2=INNOCENT
        # Row 2: A3=CRIMINAL, B3=INNOCENT, C3=CRIMINAL
        for r in range(n):
            for c in range(n):
                cell = CellId(r, c)
                idx = r * n + c
                name, job = names_jobs[idx]
                characters[cell] = Character(cell, name, job)
                status = Status.CRIMINAL if (r + c) % 2 == 0 else Status.INNOCENT
                solution[cell] = status
                clues[cell] = Fact(f"clue@{cell}", cell, status)

        initial_revealed = frozenset([CellId(0, 0)])

        return Puzzle(
            n=n,
            characters=characters,
            solution=solution,
            clues=clues,
            initial_revealed=initial_revealed,
        )

    @property
    def n(self) -> int:
        return self.puzzle.n

    def public_state(self) -> PublicState:
        """Return the current public state visible to the agent or GUI."""
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
        """Submit a status verdict for a cell."""
        if cell in self._proved:
            return VerdictResult(
                outcome=VerdictOutcome.ACCEPTED,
                cell=cell,
                revealed_clue=self.puzzle.clues.get(cell),
            )

        expected_status = self.puzzle.solution[cell]
        if status is expected_status:
            self._proved[cell] = status
            clue = self.puzzle.clues[cell]
            if clue not in self._revealed_clues:
                self._revealed_clues.append(clue)
            return VerdictResult(
                outcome=VerdictOutcome.ACCEPTED,
                cell=cell,
                revealed_clue=clue,
            )
        else:
            return VerdictResult(
                outcome=VerdictOutcome.CONTRADICTED,
                cell=cell,
                revealed_clue=None,
            )

    def is_solved(self) -> bool:
        """Return True if all cells are proved."""
        return len(self._proved) == self.n * self.n

    def restart(self) -> None:
        """Reset game state to initial revealed cards."""
        self._proved = {}
        self._revealed_clues = []
        for cell in self.puzzle.initial_revealed:
            self._proved[cell] = self.puzzle.solution[cell]
            clue = self.puzzle.clues[cell]
            if clue not in self._revealed_clues:
                self._revealed_clues.append(clue)
