"""Encode Griductive clues as DIMACS CNF."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
from typing import Literal

from griductive.logic.varmap import VarMap
from griductive.model.cell import CellId, Status
from griductive.model.clue import (
    Clue,
    Compare,
    Count,
    Different,
    Fact,
    Parity,
    Same,
)
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
    """Encode clues using selectable combinatorial or sequential cardinality CNF."""

    def __init__(
        self,
        n: int,
        encoding: Literal["combinatorial", "sequential"] = "combinatorial",
    ) -> None:
        if encoding not in ("combinatorial", "sequential"):
            raise ValueError("encoding must be 'combinatorial' or 'sequential'")
        self.varmap = VarMap(n)
        self.encoding = encoding

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

        if isinstance(clue, Parity):
            return self._encode_parity(clue)

        if isinstance(clue, Compare):
            return self._encode_compare(clue)

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

        if self.encoding == "combinatorial":
            if clue.op == Count.LE:
                return self._at_most(variables, clue.k)
            if clue.op == Count.GE:
                return self._at_least(variables, clue.k)
            return self._at_most(variables, clue.k) + self._at_least(variables, clue.k)

        return self._sequential_count(variables, clue.op, clue.k)

    @staticmethod
    def _at_most(variables: tuple[int, ...], k: int) -> list[Clause]:
        # Every set of k+1 cells must contain at least one innocent.
        return [tuple(-var for var in group) for group in combinations(variables, k + 1)]

    @staticmethod
    def _at_least(variables: tuple[int, ...], k: int) -> list[Clause]:
        # Every subset of m-k+1 cells must contain at least one criminal.
        size = len(variables) - k + 1
        return [tuple(group) for group in combinations(variables, size)]

    def _encode_parity(self, clue: Parity) -> list[Clause]:
        if clue.parity not in (Parity.EVEN, Parity.ODD):
            raise ClueError(f"unsupported parity: {clue.parity!r}")
        try:
            cells = clue.cells(self.n)
        except (TypeError, ValueError) as exc:
            raise ClueError(f"invalid parity region: {exc}") from exc
        if not cells:
            raise ClueError("parity region cannot be empty")
        variables = tuple(self._cell_var(cell) for cell in cells)

        # For small regions, forbid each assignment with the wrong parity.
        if len(variables) <= 8:
            clauses: list[Clause] = []
            wanted_odd = clue.parity == Parity.ODD
            for values in product((False, True), repeat=len(variables)):
                if sum(values) % 2 == wanted_odd:
                    continue
                # A clause falsified only by this precise assignment.
                clauses.append(
                    tuple(-var if value else var for var, value in zip(variables, values))
                )
            return clauses

        # For larger regions, chain XOR gates: t_i = t_(i-1) XOR x_i.
        previous = variables[0]
        clauses = []
        for variable in variables[1:]:
            current = self.varmap.new_aux()
            clauses.extend(
                [
                    (-current, previous, variable),
                    (-current, -previous, -variable),
                    (current, -previous, variable),
                    (current, previous, -variable),
                ]
            )
            previous = current
        clauses.append((previous if clue.parity == Parity.ODD else -previous,))
        return clauses

    def _encode_compare(self, clue: Compare) -> list[Clause]:
        if clue.op not in Compare.OPS:
            raise ClueError(f"unsupported comparison operator: {clue.op!r}")
        try:
            left_cells = clue.left_cells(self.n)
            right_cells = clue.right_cells(self.n)
        except (TypeError, ValueError) as exc:
            raise ClueError(f"invalid comparison region: {exc}") from exc
        if not left_cells or not right_cells:
            raise ClueError("comparison regions cannot be empty")
        left = tuple(self._cell_var(cell) for cell in left_cells)
        right = tuple(self._cell_var(cell) for cell in right_cells)
        union = tuple(sorted(set(left) | set(right)))

        if len(union) <= 10:
            return self._compare_direct(left, right, union, clue.op)
        return self._compare_counters(left, right, clue.op)

    @staticmethod
    def _compare_direct(
        left: tuple[int, ...], right: tuple[int, ...], union: tuple[int, ...], op: str
    ) -> list[Clause]:
        clauses: list[Clause] = []
        for values in product((False, True), repeat=len(union)):
            assignment = dict(zip(union, values))
            left_count = sum(assignment[var] for var in left)
            right_count = sum(assignment[var] for var in right)
            satisfied = {
                Compare.LT: left_count < right_count,
                Compare.LE: left_count <= right_count,
                Compare.EQ: left_count == right_count,
                Compare.GE: left_count >= right_count,
                Compare.GT: left_count > right_count,
            }[op]
            if not satisfied:
                clauses.append(
                    tuple(-var if assignment[var] else var for var in union)
                )
        return clauses

    def _make_counter(
        self, variables: tuple[int, ...]
    ) -> tuple[dict[tuple[int, int], int], list[Clause]]:
        """Build a full equivalence counter for all thresholds of a region."""
        states: dict[tuple[int, int], int] = {}
        clauses: list[Clause] = []
        for i, x_i in enumerate(variables, start=1):
            for j in range(1, i + 1):
                current = self.varmap.new_aux()
                states[(i, j)] = current
                previous_j = states.get((i - 1, j))
                previous_j_minus_1 = True if j == 1 else states.get((i - 1, j - 1))

                if previous_j is not None:
                    clauses.append((-previous_j, current))
                if previous_j_minus_1 is True:
                    clauses.append((-x_i, current))
                elif previous_j_minus_1 is not None:
                    clauses.append((-x_i, -previous_j_minus_1, current))

                if previous_j is None:
                    clauses.append((-current, x_i))
                    if previous_j_minus_1 is not True:
                        clauses.append(
                            (-current,)
                            if previous_j_minus_1 is None
                            else (-current, previous_j_minus_1)
                        )
                else:
                    clauses.append((-current, previous_j, x_i))
                    if previous_j_minus_1 is not True:
                        clauses.append(
                            (-current, previous_j)
                            if previous_j_minus_1 is None
                            else (-current, previous_j, previous_j_minus_1)
                        )
        return states, clauses

    def _compare_counters(
        self, left: tuple[int, ...], right: tuple[int, ...], op: str
    ) -> list[Clause]:
        left_states, clauses = self._make_counter(left)
        right_states, right_clauses = self._make_counter(right)
        clauses.extend(right_clauses)

        def threshold(
            states: dict[tuple[int, int], int], size: int, j: int
        ) -> bool | int:
            if j <= 0:
                return True
            if j > size:
                return False
            return states[(size, j)]

        def imply(antecedent: bool | int, consequent: bool | int) -> None:
            """Append the CNF for antecedent -> consequent with constants folded."""
            if antecedent is False or consequent is True:
                return
            if antecedent is True:
                clauses.append(()) if consequent is False else clauses.append((consequent,))
                return
            if consequent is False:
                clauses.append((-antecedent,))
            else:
                clauses.append((-antecedent, consequent))

        def add_le(
            a_states: dict[tuple[int, int], int], a_size: int,
            b_states: dict[tuple[int, int], int], b_size: int,
        ) -> None:
            for j in range(1, a_size + 1):
                imply(threshold(a_states, a_size, j), threshold(b_states, b_size, j))

        def add_lt(
            a_states: dict[tuple[int, int], int], a_size: int,
            b_states: dict[tuple[int, int], int], b_size: int,
        ) -> None:
            for j in range(0, a_size + 1):
                imply(threshold(a_states, a_size, j), threshold(b_states, b_size, j + 1))

        if op == Compare.LE:
            add_le(left_states, len(left), right_states, len(right))
        elif op == Compare.LT:
            add_lt(left_states, len(left), right_states, len(right))
        elif op == Compare.GE:
            add_le(right_states, len(right), left_states, len(left))
        elif op == Compare.GT:
            add_lt(right_states, len(right), left_states, len(left))
        else:  # EQ
            add_le(left_states, len(left), right_states, len(right))
            add_le(right_states, len(right), left_states, len(left))
        return clauses

    def _sequential_count(
        self, variables: tuple[int, ...], op: str, k: int
    ) -> list[Clause]:
        """Encode a cardinality condition with a bidirectional unary counter.

        Counter state ``s[i,j]`` means at least ``j`` of the first ``i``
        inputs are true. Each state is fully defined by
        ``s[i,j] <-> s[i-1,j] or (x_i and s[i-1,j-1])``. Full equivalence
        keeps auxiliary assignments deterministic for a given primary model.
        """
        m = len(variables)
        if op == Count.LE and k == m or op == Count.GE and k == 0:
            return []
        if op == Count.LE and k == 0:
            return [(-var,) for var in variables]
        if op == Count.GE and k == m:
            return [(var,) for var in variables]

        # Exactly k needs thresholds k and k+1. The other operators only
        # need the threshold that decides their bound.
        limit = k + 1 if op in (Count.LE, Count.EQ) else k
        limit = min(limit, m)
        states: dict[tuple[int, int], int] = {}
        clauses: list[Clause] = []

        # Build each threshold from the preceding prefix. Terms outside the
        # allocated triangle are constants: s[i,0] = True, s[i,j] = False
        # for j > i.
        for i, x_i in enumerate(variables, start=1):
            for j in range(1, min(i, limit) + 1):
                current = self.varmap.new_aux()
                states[(i, j)] = current

                previous_j = states.get((i - 1, j))  # False when j > i - 1
                previous_j_minus_1 = True if j == 1 else states.get((i - 1, j - 1))

                # previous_j -> current
                if previous_j is not None:
                    clauses.append((-previous_j, current))
                # x_i AND previous_(j-1) -> current; for j=1 the previous
                # threshold is the constant True.
                if previous_j_minus_1 is True:
                    clauses.append((-x_i, current))
                elif previous_j_minus_1 is not None:
                    clauses.append((-x_i, -previous_j_minus_1, current))

                # current -> previous_j OR (x_i AND previous_(j-1));
                # split the conjunction into two CNF clauses.
                if previous_j is None:
                    clauses.append((-current, x_i))
                    if previous_j_minus_1 is not True:
                        if previous_j_minus_1 is None:
                            clauses.append((-current,))
                        else:
                            clauses.append((-current, previous_j_minus_1))
                else:
                    clauses.append((-current, previous_j, x_i))
                    if previous_j_minus_1 is not True:
                        if previous_j_minus_1 is None:
                            clauses.append((-current, previous_j))
                        else:
                            clauses.append((-current, previous_j, previous_j_minus_1))

        def state(threshold: int) -> int | None:
            """Return s[m,threshold], simplifying the boundary constants."""
            if threshold <= 0:
                return None  # True
            if threshold > m:
                return -1  # False sentinel
            return states.get((m, threshold))

        def require_at_least(threshold: int) -> None:
            final = state(threshold)
            if final is None:
                return
            if final == -1:
                clauses.append(())
            else:
                clauses.append((final,))

        def require_at_most(threshold: int) -> None:
            final = state(threshold + 1)
            if final is None:
                clauses.append(())
            elif final != -1:
                clauses.append((-final,))

        if op == Count.LE:
            require_at_most(k)
        elif op == Count.GE:
            require_at_least(k)
        else:
            require_at_least(k)
            require_at_most(k)
        return clauses

    def _cell_var(self, cell: CellId) -> int:
        try:
            return self.varmap.var(cell)
        except (TypeError, ValueError) as exc:
            raise ClueError(f"invalid clue cell {cell!r}: {exc}") from exc

    def _distinct_pair(self, a: CellId, b: CellId) -> tuple[int, int]:
        if a == b:
            raise ClueError("SAME/DIFFERENT requires two distinct cells")
        return self._cell_var(a), self._cell_var(b)
