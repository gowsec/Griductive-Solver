"""Encode the six required Griductive clue forms as DIMACS CNF."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from griductive.logic.varmap import VarMap
from griductive.model.cell import CellId, Status
from griductive.model.clue import Clue, Count, Different, Fact, Same
from griductive.model.puzzle import PublicState


class ClueError(ValueError):
    """Raised when a clue is malformed or incompatible with the grid."""


Clause = tuple[int, ...]


@dataclass(frozen=True)
class KB:
    """CNF clauses and variable/clause statistics for one public state."""

    clauses: list[Clause]
    n_primary: int
    n_aux: int

    @property
    def n_clauses(self) -> int:
        return len(self.clauses)

    @property
    def num_vars(self) -> int:
        return self.n_primary + self.n_aux


class CNFEncoder:
    """Encode FACT, SAME, DIFFERENT and the three cardinality clues."""

    def __init__(self, n: int) -> None:
        self.varmap = VarMap(n)

    @property
    def n(self) -> int:
        return self.varmap.n

    def encode(self, clue: Clue) -> list[Clause]:
        """Return a deterministic CNF equivalent to ``clue``."""
        if isinstance(clue, Fact):
            var = self._cell_var(clue.cell)
            if clue.status is Status.CRIMINAL:
                return [(var,)]
            if clue.status is Status.INNOCENT:
                return [(-var,)]
            raise ClueError(f"unsupported FACT status: {clue.status!r}")

        if isinstance(clue, Same):
            a, b = self._distinct_pair(clue.a, clue.b)
            return [(-a, b), (a, -b)]

        if isinstance(clue, Different):
            a, b = self._distinct_pair(clue.a, clue.b)
            return [(a, b), (-a, -b)]

        if isinstance(clue, Count):
            return self._encode_count(clue)

        raise ClueError(f"unsupported clue type: {type(clue).__name__}")

    def build_kb(self, state: PublicState) -> KB:
        """Build a KB using only revealed clues and already proved statuses."""
        if not isinstance(state, PublicState):
            raise TypeError("state must be a PublicState")
        if state.n != self.n:
            raise ClueError(
                f"state grid size {state.n} does not match encoder size {self.n}"
            )

        # Each build starts fresh so auxiliary ids/statistics do not depend on
        # previous calls to encode() or build_kb().
        self.varmap = VarMap(self.n)
        clauses: list[Clause] = []
        for clue in state.revealed_clues:
            clauses.extend(self.encode(clue))
        for cell, status in sorted(state.proved.items()):
            var = self._cell_var(cell)
            if status is Status.CRIMINAL:
                clauses.append((var,))
            elif status is Status.INNOCENT:
                clauses.append((-var,))
            else:
                raise ClueError(f"unsupported proved status: {status!r}")

        return KB(clauses, self.varmap.n_primary, self.varmap.n_aux)

    def _encode_count(self, clue: Count) -> list[Clause]:
        if clue.op not in (Count.EQ, Count.GE, Count.LE):
            raise ClueError(f"unsupported count operator: {clue.op!r}")
        if isinstance(clue.k, bool) or not isinstance(clue.k, int):
            raise ClueError("count k must be an integer")
        try:
            cells = clue.cells(self.n)
        except (TypeError, ValueError) as exc:
            raise ClueError(f"invalid count region: {exc}") from exc
        if not cells:
            raise ClueError("count region cannot be empty")
        variables = tuple(self._cell_var(cell) for cell in cells)
        if not 0 <= clue.k <= len(variables):
            raise ClueError(f"count k must be between 0 and {len(variables)}")

        if clue.op == Count.LE:
            return self._at_most(variables, clue.k)
        if clue.op == Count.GE:
            return self._at_least(variables, clue.k)
        return self._at_most(variables, clue.k) + self._at_least(variables, clue.k)

    @staticmethod
    def _at_most(variables: tuple[int, ...], k: int) -> list[Clause]:
        # Every set of k+1 cells must contain at least one innocent.
        return [tuple(-var for var in group) for group in combinations(variables, k + 1)]

    @staticmethod
    def _at_least(variables: tuple[int, ...], k: int) -> list[Clause]:
        # Every subset of m-k+1 cells must contain at least one criminal.
        size = len(variables) - k + 1
        return [tuple(group) for group in combinations(variables, size)]

    def _cell_var(self, cell: CellId) -> int:
        try:
            return self.varmap.var(cell)
        except (TypeError, ValueError) as exc:
            raise ClueError(f"invalid clue cell {cell!r}: {exc}") from exc

    def _distinct_pair(self, a: CellId, b: CellId) -> tuple[int, int]:
        if a == b:
            raise ClueError("SAME/DIFFERENT requires two distinct cells")
        return self._cell_var(a), self._cell_var(b)
