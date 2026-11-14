"""Tests for GameEngine behavior with a deterministic fake oracle."""

import unittest
from dataclasses import dataclass
from enum import Enum
import json
import tempfile
from pathlib import Path

from griductive.engine.dummy_engine import VerdictOutcome
from griductive.engine.game_engine import GameEngine
from griductive.model.cell import CellId, Character, Status
from griductive.model.clue import Fact
from griductive.model.puzzle import Puzzle


class FakeVerdict(Enum):
    CRIMINAL = "CRIMINAL"
    INNOCENT = "INNOCENT"
    UNKNOWN = "UNKNOWN"
    INCONSISTENT = "INCONSISTENT"


@dataclass(frozen=True)
class FakeClassification:
    verdict: FakeVerdict
    queries: tuple[str, ...] = ()


class FakeOracle:
    def __init__(self, verdict: FakeVerdict) -> None:
        self.verdict = verdict
        self.calls: list[tuple[object, CellId]] = []

    def __call__(self, state: object, cell: CellId) -> FakeClassification:
        self.calls.append((state, cell))
        return FakeClassification(self.verdict, ("query",))


def make_puzzle() -> Puzzle:
    cells = tuple(CellId(row, col) for row in range(2) for col in range(2))
    return Puzzle(
        n=2,
        characters={cell: Character(cell, str(cell), "Unknown") for cell in cells},
        solution={
            cells[0]: Status.CRIMINAL,
            cells[1]: Status.INNOCENT,
            cells[2]: Status.INNOCENT,
            cells[3]: Status.CRIMINAL,
        },
        clues={
            cell: Fact(f"clue@{cell}", cell, Status.CRIMINAL)
            for cell in cells
        },
        initial_revealed=frozenset({cells[0]}),
    )


class GameEngineTests(unittest.TestCase):
    def test_initial_public_state_is_ordered_and_hides_solution(self) -> None:
        engine = GameEngine(make_puzzle(), FakeOracle(FakeVerdict.UNKNOWN))
        state = engine.public_state()
        self.assertEqual(tuple(state.proved), (CellId(0, 0),))
        self.assertEqual(
            state.unsolved,
            (CellId(0, 1), CellId(1, 0), CellId(1, 1)),
        )
        self.assertEqual(
            tuple(clue.id for clue in state.revealed_clues), ("clue@A1",)
        )
        self.assertFalse(hasattr(state, "solution"))
        with self.assertRaises(TypeError):
            state.proved[CellId(0, 1)] = Status.INNOCENT

    def test_accepts_oracle_verdict_without_consulting_hidden_solution(self) -> None:
        puzzle = make_puzzle()
        oracle = FakeOracle(FakeVerdict.CRIMINAL)
        engine = GameEngine(puzzle, oracle)
        cell = CellId(0, 1)

        result = engine.submit(cell, Status.CRIMINAL)

        self.assertEqual(result.outcome, VerdictOutcome.ACCEPTED)
        self.assertEqual(result.revealed_clue, puzzle.clues[cell])
        self.assertEqual(result.queries, ("query",))
        self.assertEqual(engine.public_state().proved[cell], Status.CRIMINAL)
        self.assertEqual(len(oracle.calls), 1)

    def test_unknown_inconsistent_and_contradicted_do_not_change_state(self) -> None:
        scenarios = (
            (FakeVerdict.UNKNOWN, Status.CRIMINAL, VerdictOutcome.NOT_PROVABLE),
            (FakeVerdict.INCONSISTENT, Status.CRIMINAL, VerdictOutcome.INCONSISTENT),
            (FakeVerdict.CRIMINAL, Status.INNOCENT, VerdictOutcome.CONTRADICTED),
        )
        for verdict, submitted_status, expected in scenarios:
            with self.subTest(verdict=verdict):
                engine = GameEngine(make_puzzle(), FakeOracle(verdict))
                before = engine.public_state()
                result = engine.submit(CellId(0, 1), submitted_status)
                after = engine.public_state()
                self.assertEqual(result.outcome, expected)
                self.assertIsNone(result.revealed_clue)
                self.assertEqual(after.proved, before.proved)
                self.assertEqual(after.revealed_clues, before.revealed_clues)

    def test_rejects_already_solved_cell_and_restart_restores_initial_state(self) -> None:
        engine = GameEngine(make_puzzle(), FakeOracle(FakeVerdict.INNOCENT))
        initial = engine.public_state()
        with self.assertRaisesRegex(ValueError, "already been solved"):
            engine.submit(CellId(0, 0), Status.CRIMINAL)
        engine.submit(CellId(0, 1), Status.INNOCENT)
        engine.restart()
        self.assertEqual(engine.public_state(), initial)

    def test_reports_solved_after_every_cell_is_proved(self) -> None:
        engine = GameEngine(make_puzzle(), FakeOracle(FakeVerdict.CRIMINAL))
        self.assertFalse(engine.is_solved())
        engine.submit(CellId(0, 1), Status.CRIMINAL)
        engine.submit(CellId(1, 0), Status.CRIMINAL)
        engine.submit(CellId(1, 1), Status.CRIMINAL)
        self.assertTrue(engine.is_solved())

    def test_load_constructs_engine_from_json(self) -> None:
        data = {
            "n": 1,
            "characters": {"A1": {"name": "Alex", "job": "Detective"}},
            "solution": {"A1": "CRIMINAL"},
            "initial_revealed": [],
            "clues": {
                "A1": {
                    "type": "FACT",
                    "cell": "A1",
                    "status": "CRIMINAL",
                }
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "puzzle.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            engine = GameEngine.load(str(path), FakeOracle(FakeVerdict.CRIMINAL))

        self.assertEqual(engine.n, 1)
        self.assertEqual(engine.public_state().unsolved, (CellId(0, 0),))


if __name__ == "__main__":
    unittest.main()
