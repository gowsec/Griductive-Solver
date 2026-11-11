"""DPLL SAT solver implementation for CNF formulas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
import time


class SolverTimeout(Exception):
    """Raised when DPLL solver exceeds maximum allowed runtime."""


@dataclass
class SolverStats:
    """Statistics recorded during DPLL execution."""

    decisions: int = 0
    propagations: int = 0
    backtracks: int = 0
    runtime: float = 0.0

    def add(self, other: SolverStats) -> None:
        """Accumulate statistics from another solver run."""
        self.decisions += other.decisions
        self.propagations += other.propagations
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
            var = abs(lit)
            val = lit > 0
            if var in assignment and assignment[var] != val:
                stats.runtime = time.perf_counter() - start_time
                return SolveResult(satisfiable=False, model=None, stats=stats)
            assignment[var] = val

        satisfiable, final_assignment = self._dpll(
            clause_list, num_vars, assignment, stats, deadline
        )

        stats.runtime = time.perf_counter() - start_time

        if satisfiable:
            full_model = {v: final_assignment.get(v, False) for v in range(1, num_vars + 1)}
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
            raise SolverTimeout("DPLL solver timed out")

        assignment, clauses, conflict = self._unit_propagate(clauses, assignment, stats)
        if conflict:
            return False, {}

        if not clauses:
            return True, assignment

        unassigned_var = next((v for v in range(1, num_vars + 1) if v not in assignment), None)
        if unassigned_var is None:
            return True, assignment

        stats.decisions += 1

        # Branch True
        assignment_true = dict(assignment)
        assignment_true[unassigned_var] = True
        sat, res = self._dpll(clauses + [(unassigned_var,)], num_vars, assignment_true, stats, deadline)
        if sat:
            return True, res

        stats.backtracks += 1

        # Branch False
        assignment_false = dict(assignment)
        assignment_false[unassigned_var] = False
        sat, res = self._dpll(clauses + [(-unassigned_var,)], num_vars, assignment_false, stats, deadline)
        if sat:
            return True, res

        return False, {}

    def _unit_propagate(
        self,
        clauses: list[tuple[int, ...]],
        assignment: dict[dict[int, bool]],
        stats: SolverStats,
    ) -> tuple[dict[int, bool], list[tuple[int, ...]], bool]:
        current_assignment = dict(assignment)
        current_clauses = list(clauses)

        while True:
            new_clauses: list[tuple[int, ...]] = []
            unit_lit: int | None = None

            for clause in current_clauses:
                satisfied = False
                unassigned_lits: list[int] = []

                for lit in clause:
                    var = abs(lit)
                    val = lit > 0
                    if var in current_assignment:
                        if current_assignment[var] == val:
                            satisfied = True
                            break
                    else:
                        unassigned_lits.append(lit)

                if satisfied:
                    continue
                if not unassigned_lits:
                    return current_assignment, current_clauses, True

                new_clause = tuple(unassigned_lits)
                new_clauses.append(new_clause)
                if len(new_clause) == 1 and unit_lit is None:
                    unit_lit = new_clause[0]

            current_clauses = new_clauses

            if unit_lit is not None:
                stats.propagations += 1
                var = abs(unit_lit)
                current_assignment[var] = (unit_lit > 0)
            else:
                break

        return current_assignment, current_clauses, False
