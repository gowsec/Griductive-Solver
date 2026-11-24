"""DPLL SAT solver implementation for CNF formulas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
import time


class SolverTimeout(Exception):
    """Raised when DPLL solver exceeds maximum allowed runtime."""

    def __init__(
        self,
        message: str = "DPLL solver timed out",
        stats: SolverStats | None = None,
        sat_calls: int = 1,
    ) -> None:
        super().__init__(message)
        self.stats = stats
        self.sat_calls = sat_calls


@dataclass
class SolverStats:
    """Statistics recorded during DPLL execution."""

    decisions: int = 0
    propagations: int = 0
    conflicts: int = 0
    backtracks: int = 0
    runtime: float = 0.0

    def add(self, other: SolverStats) -> None:
        """Accumulate statistics from another solver run."""
        self.decisions += other.decisions
        self.propagations += other.propagations
        self.conflicts += other.conflicts
        self.backtracks += other.backtracks
        self.runtime += other.runtime


@dataclass
class SolveResult:
    """Result of solving a CNF formula."""

    satisfiable: bool
    model: dict[int, bool] | None
    stats: SolverStats


class DPLLSolver:
    """A deterministic DPLL SAT solver with unit propagation and backtracking."""

    def __init__(self, pure_literal: bool = False) -> None:
        self.pure_literal = pure_literal

    def solve(
        self,
        clauses: Sequence[Sequence[int]],
        num_vars: int,
        assumptions: Sequence[int] = (),
        timeout: float | None = None,
    ) -> SolveResult:
        """Solve a CNF formula under optional assumptions."""
        start_time = time.perf_counter()
        stats = SolverStats()
        deadline = (start_time + timeout) if timeout is not None else None

        clause_list = [tuple(c) for c in clauses]
        assignment: dict[int, bool] = {}

        for lit in assumptions:
            if lit == 0:
                raise ValueError("Assumption literal cannot be 0.")
            var = abs(lit)
            val = lit > 0
            if var in assignment and assignment[var] != val:
                stats.conflicts += 1
                stats.runtime = time.perf_counter() - start_time
                return SolveResult(satisfiable=False, model=None, stats=stats)
            assignment[var] = val

        try:
            satisfiable, final_assignment = self._dpll(
                clause_list, num_vars, assignment, stats, deadline
            )
        except SolverTimeout as exc:
            stats.runtime = time.perf_counter() - start_time
            exc.stats = stats
            raise

        stats.runtime = time.perf_counter() - start_time

        if satisfiable:
            full_model = {
                v: final_assignment.get(v, False) for v in range(1, num_vars + 1)
            }
            return SolveResult(satisfiable=True, model=full_model, stats=stats)
        return SolveResult(satisfiable=False, model=None, stats=stats)

    def _dpll(
        self,
        clauses: list[tuple[int, ...]],
        num_vars: int,
        assignment: dict[int, bool],
        stats: SolverStats,
        deadline: float | None,
    ) -> tuple[bool, dict[int, bool]]:
        if deadline is not None and time.perf_counter() > deadline:
            raise SolverTimeout("DPLL solver timed out", stats=stats)

        assignment, clauses, conflict = self._unit_propagate(
            clauses, assignment, stats, deadline
        )
        if conflict:
            return False, {}

        if self.pure_literal and clauses:
            assignment, clauses = self._eliminate_pure_literals(clauses, assignment)

        if not clauses:
            return True, assignment

        # Chỉ chọn biến có chỉ số nhỏ nhất còn xuất hiện trong các clause chưa thỏa
        unassigned_var = min(abs(lit) for clause in clauses for lit in clause)
        stats.decisions += 1

        # Branch True
        assignment_true = dict(assignment)
        assignment_true[unassigned_var] = True
        sat, res = self._dpll(clauses, num_vars, assignment_true, stats, deadline)
        if sat:
            return True, res

        stats.backtracks += 1

        # Branch False
        assignment_false = dict(assignment)
        assignment_false[unassigned_var] = False
        sat, res = self._dpll(clauses, num_vars, assignment_false, stats, deadline)
        if sat:
            return True, res

        return False, {}

    def _unit_propagate(
        self,
        clauses: list[tuple[int, ...]],
        assignment: dict[int, bool],
        stats: SolverStats,
        deadline: float | None = None,
    ) -> tuple[dict[int, bool], list[tuple[int, ...]], bool]:
        current_assignment = dict(assignment)
        current_clauses = clauses

        while True:
            if deadline is not None and time.perf_counter() > deadline:
                raise SolverTimeout("DPLL solver timed out", stats=stats)

            new_clauses: list[tuple[int, ...]] = []
            propagated = False

            for clause in current_clauses:
                satisfied = False
                unassigned_lits: list[int] = []

                for lit in clause:
                    var = abs(lit)
                    val = lit > 0
                    assigned = current_assignment.get(var)
                    if assigned is not None:
                        if assigned == val:
                            satisfied = True
                            break
                    else:
                        unassigned_lits.append(lit)

                if satisfied:
                    continue
                if not unassigned_lits:
                    stats.conflicts += 1
                    return current_assignment, current_clauses, True

                if len(unassigned_lits) == 1:
                    unit_lit = unassigned_lits[0]
                    current_assignment[abs(unit_lit)] = unit_lit > 0
                    stats.propagations += 1
                    propagated = True
                else:
                    new_clauses.append(tuple(unassigned_lits))

            current_clauses = new_clauses
            if not propagated:
                break

        return current_assignment, current_clauses, False

    def _eliminate_pure_literals(
        self,
        clauses: list[tuple[int, ...]],
        assignment: dict[int, bool],
    ) -> tuple[dict[int, bool], list[tuple[int, ...]]]:
        """Assign literals that appear with only one polarity in remaining clauses."""
        current_assignment = dict(assignment)
        current_clauses = clauses

        while True:
            polarities: dict[int, set[bool]] = {}
            for clause in current_clauses:
                for lit in clause:
                    var = abs(lit)
                    if var not in current_assignment:
                        polarities.setdefault(var, set()).add(lit > 0)

            pure_vars = {
                var: next(iter(pols))
                for var, pols in polarities.items()
                if len(pols) == 1
            }
            if not pure_vars:
                break

            current_assignment.update(pure_vars)
            current_clauses = [
                clause
                for clause in current_clauses
                if not any(
                    current_assignment.get(abs(lit)) == (lit > 0) for lit in clause
                )
            ]

        return current_assignment, current_clauses
