"""Unit tests for the DPLL SAT solver (griductive.logic.dpll)."""

from __future__ import annotations

import pytest
from griductive.logic.dpll import DPLLSolver, SolveResult, SolverStats, SolverTimeout


def is_model_valid(clauses: list[list[int]], model: dict[int, bool]) -> bool:
    """Helper to verify that a returned model satisfies all CNF clauses."""
    for clause in clauses:
        if not any(
            (model[abs(lit)] if lit > 0 else not model[abs(lit)])
            for lit in clause
        ):
            return False
    return True


class TestUnitPropagationAndConflict:
    """Test unit propagation chains and conflict detection."""

    def test_unit_propagation_chain_without_branching(self) -> None:
        """
        CNF: (x1) ^ (-x1 v x2) ^ (-x2 v -x3) ^ (x3 v x4)
        Chain: x1=True -> x2=True -> x3=False -> x4=True.
        Should solve purely via 4 unit propagations and 0 decisions.
        """
        clauses = [
            [1],
            [-1, 2],
            [-2, -3],
            [3, 4],
        ]
        solver = DPLLSolver()
        result = solver.solve(clauses, num_vars=4)

        assert result.satisfiable is True
        assert result.model == {1: True, 2: True, 3: False, 4: True}
        assert result.stats.propagations == 4
        assert result.stats.decisions == 0
        assert result.stats.backtracks == 0
        assert result.stats.conflicts == 0

    def test_direct_unit_conflict(self) -> None:
        """
        CNF: (x1) ^ (-x1 v x2) ^ (-x1 v -x2)
        Unit propagation forces x1=True, x2=True, and then clause (-x1 v -x2) becomes empty.
        """
        clauses = [
            [1],
            [-1, 2],
            [-1, -2],
        ]
        solver = DPLLSolver()
        result = solver.solve(clauses, num_vars=2)

        assert result.satisfiable is False
        assert result.model is None
        assert result.stats.conflicts >= 1
        assert result.stats.decisions == 0

    def test_empty_clause_immediately_unsat(self) -> None:
        """An empty clause [] in the formula represents immediate conflict."""
        clauses = [[1, 2], []]
        solver = DPLLSolver()
        result = solver.solve(clauses, num_vars=2)

        assert result.satisfiable is False
        assert result.model is None
        assert result.stats.conflicts == 1


class TestBranchingAndBacktracking:
    """Test deterministic branching (True then False) and backtracking."""

    def test_branching_and_backtrack_to_false_branch(self) -> None:
        """
        Solver always picks smallest unassigned variable (x1) and tries True first.
        Clauses:
            (-x1 v x2) ^ (-x1 v -x2) ^ (x1 v x3)
        - Branch 1: x1=True -> forces x2=True and x2=False -> Conflict!
        - Backtrack (backtracks += 1) -> Branch 2: x1=False -> forces x3=True -> SAT!
        """
        clauses = [
            [-1, 2],
            [-1, -2],
            [1, 3],
        ]
        solver = DPLLSolver()
        result = solver.solve(clauses, num_vars=3)

        assert result.satisfiable is True
        assert result.model is not None
        assert result.model[1] is False
        assert result.model[3] is True
        assert is_model_valid(clauses, result.model)
        assert result.stats.decisions == 1
        assert result.stats.backtracks == 1
        assert result.stats.conflicts == 1

    def test_unsat_2var_all_combinations(self) -> None:
        """Full 2-variable contradiction requires branching and backtracking."""
        clauses = [
            [1, 2],
            [1, -2],
            [-1, 2],
            [-1, -2],
        ]
        solver = DPLLSolver()
        result = solver.solve(clauses, num_vars=2)

        assert result.satisfiable is False
        assert result.model is None
        assert result.stats.decisions == 1
        assert result.stats.backtracks == 1
        assert result.stats.conflicts == 2


class TestAssumptionsAndStats:
    """Test solving under assumptions, SolverStats accumulation, and timeout."""

    def test_assumptions_select_models_and_detect_unsat(self) -> None:
        """XOR formula: (x1 v x2) ^ (-x1 v -x2)."""
        clauses = [
            [1, 2],
            [-1, -2],
        ]
        solver = DPLLSolver()

        # Force x1 = True -> x2 must be False
        res_true = solver.solve(clauses, num_vars=2, assumptions=[1])
        assert res_true.satisfiable is True
        assert res_true.model == {1: True, 2: False}
        assert res_true.stats.propagations == 1
        assert res_true.stats.decisions == 0

        # Force x1 = False -> x2 must be True
        res_false = solver.solve(clauses, num_vars=2, assumptions=[-1])
        assert res_false.satisfiable is True
        assert res_false.model == {1: False, 2: True}

        # Contradictory assumptions with formula: x1=True, x2=True
        res_unsat = solver.solve(clauses, num_vars=2, assumptions=[1, 2])
        assert res_unsat.satisfiable is False
        assert res_unsat.model is None
        assert res_unsat.stats.conflicts == 1

    def test_contradictory_assumptions_short_circuit(self) -> None:
        """Passing [1, -1] in assumptions must fail before calling _dpll."""
        solver = DPLLSolver()
        res = solver.solve([[1, 2]], num_vars=2, assumptions=[1, -1])

        assert res.satisfiable is False
        assert res.model is None
        assert res.stats.conflicts == 1
        assert res.stats.decisions == 0

    def test_solver_stats_accumulation(self) -> None:
        """Test SolverStats.add() method."""
        s1 = SolverStats(decisions=2, propagations=5, conflicts=1, backtracks=1, runtime=0.01)
        s2 = SolverStats(decisions=3, propagations=4, conflicts=2, backtracks=2, runtime=0.02)
        s1.add(s2)

        assert s1.decisions == 5
        assert s1.propagations == 9
        assert s1.conflicts == 3
        assert s1.backtracks == 3
        assert s1.runtime == pytest.approx(0.03)

    def test_solver_timeout(self) -> None:
        """Passing a negative or zero timeout should raise SolverTimeout."""
        solver = DPLLSolver()
        with pytest.raises(SolverTimeout):
            solver.solve([[1, 2], [-1, 2]], num_vars=2, timeout=-1.0)