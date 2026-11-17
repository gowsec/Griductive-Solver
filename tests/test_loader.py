"""Tests for JSON puzzle parsing and validation."""

import json
import tempfile
import unittest
from pathlib import Path

from griductive.io.loader import PuzzleError, load_puzzle
from griductive.model.cell import CellId, Status
from griductive.model.clue import Compare, Count, Different, Fact, Parity, Same
from griductive.model.puzzle import Puzzle
from griductive.model.region import RegionKind


def valid_puzzle_data() -> dict[str, object]:
    cells = [
        "A1", "B1", "C1",
        "A2", "B2", "C2",
        "A3", "B3", "C3",
    ]
    statuses = {
        "A1": "CRIMINAL", "B1": "INNOCENT", "C1": "CRIMINAL",
        "A2": "INNOCENT", "B2": "CRIMINAL", "C2": "INNOCENT",
        "A3": "CRIMINAL", "B3": "INNOCENT", "C3": "CRIMINAL",
    }
    return {
        "n": 3,
        "characters": {
            cell: {"name": f"Character {cell}", "job": "Investigator"}
            for cell in cells
        },
        "solution": statuses,
        "initial_revealed": ["A1"],
        "clues": {
            "A1": {"type": "FACT", "cell": "A1", "status": "CRIMINAL"},
            "B1": {"type": "SAME", "a": "A1", "b": "C1"},
            "C1": {"type": "DIFFERENT", "a": "A1", "b": "B1"},
            "A2": {
                "type": "EXACTLY", "k": 2,
                "region": {"kind": "ROW", "row": 1},
            },
            "B2": {
                "type": "AT_LEAST", "k": 1,
                "region": {
                    "kind": "CELLS",
                    "cells": ["A3", "B3", "C3"],
                },
            },
            "C2": {
                "type": "AT_MOST", "k": 1,
                "region": {"kind": "COL", "col": "B"},
            },
            "A3": {
                "type": "PARITY", "parity": "ODD",
                "region": {"kind": "ROW", "row": 2},
            },
            "B3": {
                "type": "COMPARE", "op": "GT",
                "left": {"kind": "COL", "col": "A"},
                "right": {"kind": "COL", "col": "B"},
            },
            "C3": {"type": "FACT", "cell": "C3", "status": "CRIMINAL"},
        },
    }


class PuzzleLoaderTests(unittest.TestCase):
    def load_data(self, data: object) -> Puzzle:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "puzzle.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return load_puzzle(path)

    def test_loads_all_clue_types_and_converts_region_coordinates(self) -> None:
        puzzle = self.load_data(valid_puzzle_data())
        self.assertEqual(puzzle.n, 3)
        self.assertEqual(len(puzzle.characters), 9)
        self.assertEqual(len(puzzle.solution), 9)
        self.assertEqual(len(puzzle.clues), 9)
        self.assertEqual(puzzle.initial_revealed, frozenset({CellId(0, 0)}))
        self.assertEqual(puzzle.clues[CellId(0, 0)], Fact(
            "clue@A1", CellId(0, 0), Status.CRIMINAL
        ))
        self.assertIsInstance(puzzle.clues[CellId(0, 1)], Same)
        self.assertIsInstance(puzzle.clues[CellId(0, 2)], Different)
        count = puzzle.clues[CellId(1, 0)]
        self.assertIsInstance(count, Count)
        self.assertEqual(count.op, Count.EQ)
        self.assertEqual(count.region.kind, RegionKind.ROW)
        self.assertEqual(count.region.row, 0)
        self.assertEqual(puzzle.clues[CellId(2, 0)].parity, Parity.ODD)
        compare = puzzle.clues[CellId(2, 1)]
        self.assertIsInstance(compare, Compare)
        self.assertEqual(compare.op, Compare.GT)
        self.assertTrue(all(
            f"clue@{clue_id}" == clue.id for clue_id, clue in puzzle.clues.items()
        ))

    def test_loaded_mappings_are_immutable_and_deterministic(self) -> None:
        data = valid_puzzle_data()
        data["characters"] = dict(reversed(list(data["characters"].items())))
        puzzle = self.load_data(data)
        self.assertEqual(
            list(puzzle.characters),
            [CellId(row, col) for row in range(3) for col in range(3)],
        )
        with self.assertRaises(TypeError):
            puzzle.solution[CellId(0, 0)] = Status.INNOCENT

    def test_rejects_invalid_json_and_nonpositive_grid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(PuzzleError, "invalid JSON"):
                load_puzzle(path)
        data = valid_puzzle_data()
        data["n"] = True
        with self.assertRaisesRegex(PuzzleError, r"\$\.n"):
            self.load_data(data)

    def test_rejects_missing_or_unknown_cells(self) -> None:
        data = valid_puzzle_data()
        del data["clues"]["C3"]
        with self.assertRaisesRegex(PuzzleError, "missing entries"):
            self.load_data(data)

        data = valid_puzzle_data()
        data["clues"]["Z9"] = {"type": "FACT", "cell": "A1", "status": "CRIMINAL"}
        with self.assertRaisesRegex(PuzzleError, "outside"):
            self.load_data(data)

    def test_rejects_invalid_clue_schema_and_region_values(self) -> None:
        data = valid_puzzle_data()
        data["clues"]["A1"] = {"type": "NOT_A_CLUE"}
        with self.assertRaisesRegex(PuzzleError, "unsupported clue type"):
            self.load_data(data)

        data = valid_puzzle_data()
        data["clues"]["A2"]["k"] = 4
        with self.assertRaisesRegex(PuzzleError, r"\$\.clues\.A2\.k"):
            self.load_data(data)

        data = valid_puzzle_data()
        data["clues"]["A2"]["region"]["row"] = 0
        with self.assertRaisesRegex(PuzzleError, "1 and 3"):
            self.load_data(data)

    def test_rejects_initial_revealed_unknown_or_duplicate_cell(self) -> None:
        data = valid_puzzle_data()
        data["initial_revealed"] = ["Z9"]
        with self.assertRaisesRegex(PuzzleError, "outside"):
            self.load_data(data)

        data = valid_puzzle_data()
        data["initial_revealed"] = ["A1", "A1"]
        with self.assertRaisesRegex(PuzzleError, "duplicate"):
            self.load_data(data)

    def test_rejects_solution_that_violates_a_clue(self) -> None:
        data = valid_puzzle_data()
        data["solution"]["A1"] = "INNOCENT"
        with self.assertRaisesRegex(PuzzleError, "not satisfied"):
            self.load_data(data)


if __name__ == "__main__":
    unittest.main()
