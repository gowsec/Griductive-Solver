"""Brute-force checks for the sample puzzles."""

import itertools
import unittest
from pathlib import Path
from types import SimpleNamespace

from griductive.engine.dummy_engine import VerdictOutcome
from griductive.engine.game_engine import GameEngine
from griductive.io.loader import load_puzzle
from griductive.model.cell import CellId, Status
from griductive.model.puzzle import PublicState

try:
    from griductive.logic.semantics import holds
except ModuleNotFoundError as error:
    if error.name != "griductive.logic.semantics":
        raise
    holds = None


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PUZZLES = (ROOT / "puzzles/3x3_01.json", ROOT / "puzzles/4x4_01.json")
SEMANTICS_AVAILABLE = holds is not None


class SamplePuzzleTests(unittest.TestCase):
    def test_puzzles_load_and_initial_state_is_valid(self) -> None:
        for path in SAMPLE_PUZZLES:
            with self.subTest(path=path.name):
                puzzle = load_puzzle(path)
                self.assertIn(puzzle.n, (3, 4))
                self.assertEqual(len(puzzle.characters), puzzle.n**2)
                self.assertEqual(len(puzzle.clues), puzzle.n**2)
                self.assertEqual(puzzle.initial_revealed, frozenset({CellId(0, 0)}))

    @unittest.skipIf(
        not SEMANTICS_AVAILABLE,
        "waiting for griductive.logic.semantics to be merged into dev",
    )
    def test_each_puzzle_has_exactly_one_model_by_semantics(self) -> None:
        assert holds is not None
        for path in SAMPLE_PUZZLES:
            with self.subTest(path=path.name):
                puzzle = load_puzzle(path)
                cells = tuple(
                    CellId(row, col)
                    for row in range(puzzle.n)
                    for col in range(puzzle.n)
                )
                models: list[dict[CellId, bool]] = []
                for values in itertools.product((False, True), repeat=len(cells)):
                    assignment = dict(zip(cells, values))
                    if all(
                        holds(clue, assignment, puzzle.n)
                        for clue in puzzle.clues.values()
                    ):
                        models.append(assignment)
                        if len(models) > 1:
                            break

                self.assertEqual(len(models), 1)
                unique_model = models[0]
                self.assertEqual(
                    unique_model,
                    {
                        cell: status is Status.CRIMINAL
                        for cell, status in puzzle.solution.items()
                    },
                )

    @unittest.skipIf(
        not SEMANTICS_AVAILABLE,
        "waiting for griductive.logic.semantics to be merged into dev",
    )
    def test_game_engine_reveals_each_puzzle_from_public_clues(self) -> None:
        assert holds is not None

        def oracle(state: PublicState, cell: CellId) -> SimpleNamespace:
            unknown_cells = tuple(state.unsolved)
            possibilities: set[bool] = set()
            for values in itertools.product((False, True), repeat=len(unknown_cells)):
                assignment = dict(state.proved)
                assignment.update(zip(unknown_cells, values))
                if all(
                    holds(clue, assignment, state.n)
                    for clue in state.revealed_clues
                ):
                    possibilities.add(assignment[cell])
                    if len(possibilities) == 2:
                        break

            if not possibilities:
                verdict = "INCONSISTENT"
            elif possibilities == {True}:
                verdict = "CRIMINAL"
            elif possibilities == {False}:
                verdict = "INNOCENT"
            else:
                verdict = "UNKNOWN"
            return SimpleNamespace(verdict=verdict, queries=())

        for path in SAMPLE_PUZZLES:
            with self.subTest(path=path.name):
                engine = GameEngine.load(str(path), oracle)
                while engine.public_state().unsolved:
                    state = engine.public_state()
                    cell = state.unsolved[0]
                    classification = oracle(state, cell)
                    self.assertIn(
                        classification.verdict, ("CRIMINAL", "INNOCENT")
                    )
                    result = engine.reveal(
                        cell, Status[classification.verdict]
                    )
                    self.assertIs(result.outcome, VerdictOutcome.ACCEPTED)

                self.assertEqual(
                    engine.public_state().proved,
                    engine.puzzle.solution,
                )


if __name__ == "__main__":
    unittest.main()
