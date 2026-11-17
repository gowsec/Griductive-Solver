"""Unit tests for uniqueness checking and blocking clause generation."""

import unittest

from griductive.logic.dpll import DPLLSolver
from griductive.logic.encoder import CNFEncoder
from griductive.logic.uniqueness import (
    UniquenessReport,
    check_uniqueness,
    check_uniqueness_cnf,
    make_blocking_clause,
)
from griductive.model.cell import CellId, Status
from griductive.model.clue import Fact
from griductive.model.puzzle import PublicState


class UniquenessTests(unittest.TestCase):
    def test_make_blocking_clause(self) -> None:
        model = {1: True, 2: False, 3: True, 4: False}
        clause = make_blocking_clause(model, 4)
        self.assertEqual(clause, (-1, 2, -3, 4))

    def test_check_uniqueness_cnf_unique(self) -> None:
        # Clauses for 2 vars forcing var 1=True, var 2=False
        clauses = [(1,), (-2,)]
        report = check_uniqueness_cnf(clauses, n_primary=2, num_vars=2)
        self.assertEqual(report.status, "UNIQUE")
        self.assertEqual(report.models_found, 1)
        self.assertEqual(report.models[0][1], True)
        self.assertEqual(report.models[0][2], False)

    def test_check_uniqueness_cnf_not_unique(self) -> None:
        # Clauses with 2 primary vars and no clauses -> 4 models possible
        clauses = []
        report = check_uniqueness_cnf(clauses, n_primary=2, num_vars=2)
        self.assertEqual(report.status, "NOT_UNIQUE")
        self.assertEqual(report.models_found, 2)
        self.assertNotEqual(report.models[0], report.models[1])

    def test_check_uniqueness_cnf_unsat(self) -> None:
        clauses = [(1,), (-1,)]
        report = check_uniqueness_cnf(clauses, n_primary=1, num_vars=1)
        self.assertEqual(report.status, "UNSAT")
        self.assertEqual(report.models_found, 0)
        self.assertEqual(len(report.models), 0)

    def test_check_uniqueness_on_grid_clues(self) -> None:
        n = 2
        # Grid 2x2 has 4 cells: A1, B1, A2, B2
        # Force all 4 cells with Facts
        clues = [
            Fact("c1", CellId(0, 0), Status.CRIMINAL),
            Fact("c2", CellId(0, 1), Status.INNOCENT),
            Fact("c3", CellId(1, 0), Status.INNOCENT),
            Fact("c4", CellId(1, 1), Status.CRIMINAL),
        ]
        report = check_uniqueness(clues, n=n)
        self.assertEqual(report.status, "UNIQUE")
        self.assertEqual(report.models_found, 1)
        model = report.models[0]
        self.assertEqual(model[CellId(0, 0)], Status.CRIMINAL)
        self.assertEqual(model[CellId(0, 1)], Status.INNOCENT)

    def test_check_uniqueness_with_public_state(self) -> None:
        n = 2
        clues = (
            Fact("c1", CellId(0, 0), Status.CRIMINAL),
            Fact("c2", CellId(0, 1), Status.INNOCENT),
        )
        proved = {CellId(1, 0): Status.INNOCENT, CellId(1, 1): Status.CRIMINAL}
        unsolved = (CellId(0, 0), CellId(0, 1))
        state = PublicState(n=n, revealed_clues=clues, proved=proved, unsolved=unsolved)

        report = check_uniqueness(state)
        self.assertEqual(report.status, "UNIQUE")
        self.assertEqual(report.models_found, 1)
        model = report.models[0]
        self.assertEqual(model[CellId(0, 0)], Status.CRIMINAL)
        self.assertEqual(model[CellId(0, 1)], Status.INNOCENT)
        self.assertEqual(model[CellId(1, 0)], Status.INNOCENT)
        self.assertEqual(model[CellId(1, 1)], Status.CRIMINAL)


if __name__ == "__main__":
    unittest.main()
