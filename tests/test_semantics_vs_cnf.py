"""Exhaustive semantic-vs-CNF checks for the supported clue types."""

from __future__ import annotations

import itertools
import unittest
from typing import Literal

from griductive.logic.dpll import DPLLSolver
from griductive.logic.encoder import CNFEncoder
from griductive.logic.semantics import holds
from griductive.model.cell import CellId, Status
from griductive.model.clue import Clue, Compare, Count, Different, Fact, Parity, Same
from griductive.model.region import Region, RegionKind


class SemanticsVsCNFTests(unittest.TestCase):
    def test_holds_evaluates_each_clue_type(self) -> None:
        criminal_cells = {CellId(0, 0), CellId(1, 1)}
        assignment = {
            CellId(row, col): CellId(row, col) in criminal_cells
            for row in range(3)
            for col in range(3)
        }
        row0 = Region(RegionKind.ROW, row=0)
        row1 = Region(RegionKind.ROW, row=1)
        row2 = Region(RegionKind.ROW, row=2)
        cases = (
            (Fact("fact_criminal", CellId(0, 0), Status.CRIMINAL), True),
            (Fact("fact_innocent", CellId(2, 2), Status.INNOCENT), True),
            (Same("same", CellId(0, 0), CellId(1, 1)), True),
            (Different("different", CellId(0, 0), CellId(0, 1)), True),
            (Count("count_eq", Count.EQ, 1, row0), True),
            (Count("count_ge", Count.GE, 1, row0), True),
            (Count("count_le", Count.LE, 1, row0), True),
            (Parity("parity_odd", Parity.ODD, row0), True),
            (Parity("parity_even", Parity.EVEN, row2), True),
            (Compare("compare_lt", row2, Compare.LT, row0), True),
            (Compare("compare_le", row0, Compare.LE, row1), True),
            (Compare("compare_eq", row0, Compare.EQ, row1), True),
            (Compare("compare_ge", row1, Compare.GE, row0), True),
            (Compare("compare_gt", row0, Compare.GT, row2), True),
        )
        for clue, expected in cases:
            with self.subTest(clue=clue):
                self.assertEqual(holds(clue, assignment, n=3), expected)

    def _assert_equivalent_for_all_assignments(
        self,
        clue: Clue,
        n: int,
        encoding: Literal["combinatorial", "sequential"] = "combinatorial",
    ) -> None:
        encoder = CNFEncoder(n, encoding=encoding)
        clauses = encoder.encode(clue)
        solver = DPLLSolver()
        cells = tuple(CellId(row, col) for row in range(n) for col in range(n))

        for values in itertools.product((False, True), repeat=n * n):
            assignment = dict(zip(cells, values))
            assumptions = tuple(
                index if value else -index
                for index, value in enumerate(values, start=1)
            )
            result = solver.solve(
                clauses,
                num_vars=encoder.varmap.n_primary + encoder.varmap.n_aux,
                assumptions=assumptions,
            )
            self.assertEqual(
                result.satisfiable,
                holds(clue, assignment, n),
                msg=f"{clue!r} disagrees for assignment {values!r}",
            )

    def test_all_clue_types_match_cnf_for_every_3x3_assignment(self) -> None:
        row = Region(RegionKind.ROW, row=0)
        column = Region(RegionKind.COL, col=0)
        all_cells = Region(
            RegionKind.CELLS,
            cells=tuple(CellId(row, col) for row in range(3) for col in range(3)),
        )
        clues = [
            Fact("fact_criminal", CellId(0, 0), Status.CRIMINAL),
            Fact("fact_innocent", CellId(2, 2), Status.INNOCENT),
            Same("same", CellId(0, 0), CellId(1, 1)),
            Different("different", CellId(0, 0), CellId(1, 1)),
            Count("count_eq", Count.EQ, 1, row),
            Count("count_ge", Count.GE, 2, row),
            Count("count_le", Count.LE, 1, row),
            Parity("parity_even", Parity.EVEN, row),
            # Nine inputs exercise the XOR-chain encoding, including aux vars.
            Parity("parity_odd_large", Parity.ODD, all_cells),
            # These regions overlap at A1; that cell contributes to both sums.
            *(
                Compare(f"compare_{op.lower()}", row, op, column)
                for op in sorted(Compare.OPS)
            ),
        ]

        for clue in clues:
            with self.subTest(clue=clue):
                self._assert_equivalent_for_all_assignments(clue, n=3)

        # Exercise both cardinality encodings against the same truth condition.
        for clue in clues[4:7]:
            with self.subTest(clue=clue, encoding="sequential"):
                self._assert_equivalent_for_all_assignments(
                    clue, n=3, encoding="sequential"
                )

    def test_compare_counter_matches_semantics_for_all_assignments(self) -> None:
        # The union has 11 cells, forcing COMPARE onto its counter encoding.
        cells = tuple(CellId(index // 4, index % 4) for index in range(11))
        left = Region(RegionKind.CELLS, cells=cells[:6])
        right = Region(RegionKind.CELLS, cells=cells[5:])
        solver = DPLLSolver()

        for op in sorted(Compare.OPS):
            clue = Compare(f"large_{op.lower()}", left, op, right)
            encoder = CNFEncoder(4)
            clauses = encoder.encode(clue)
            for values in itertools.product((False, True), repeat=len(cells)):
                assignment = dict(zip(cells, values))
                assumptions = tuple(
                    encoder.varmap.var(cell) if value else -encoder.varmap.var(cell)
                    for cell, value in zip(cells, values)
                )
                result = solver.solve(
                    clauses,
                    num_vars=encoder.varmap.n_primary + encoder.varmap.n_aux,
                    assumptions=assumptions,
                )
                self.assertEqual(
                    result.satisfiable,
                    holds(clue, assignment, n=4),
                    msg=f"{clue!r} disagrees for assignment {values!r}",
                )


if __name__ == "__main__":
    unittest.main()
