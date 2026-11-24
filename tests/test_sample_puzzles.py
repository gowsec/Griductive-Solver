"""Brute-force checks for the sample puzzles."""

import itertools
import unittest
from importlib import import_module
from pathlib import Path

from griductive.engine.dummy_engine import VerdictOutcome
from griductive.engine.game_engine import GameEngine
from griductive.io.loader import PuzzleError, load_puzzle
from griductive.logic.agent import LogicAgent
from griductive.logic.uniqueness import check_uniqueness
from griductive.experiments.runner import run_puzzle
from griductive.model.cell import CellId, Status
from griductive.model.clue import Compare, Count, Different, Parity

try:
    holds = import_module("griductive.logic.semantics").holds
except ModuleNotFoundError as error:
    if error.name != "griductive.logic.semantics":
        raise
    holds = None


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PUZZLES = (
    ROOT / "puzzles/3x3_01.json",
    ROOT / "puzzles/4x4_01.json",
    ROOT / "puzzles/5x5_01.json",
)
CLASSIFIABLE_PUZZLES = SAMPLE_PUZZLES
BRUTE_FORCE_PUZZLES = SAMPLE_PUZZLES[:2]
SEMANTICS_AVAILABLE = holds is not None


class SamplePuzzleTests(unittest.TestCase):
    def test_puzzles_load_and_initial_state_is_valid(self) -> None:
        for path in SAMPLE_PUZZLES:
            with self.subTest(path=path.name):
                puzzle = load_puzzle(path)
                self.assertIn(puzzle.n, (3, 4, 5))
                self.assertEqual(len(puzzle.characters), puzzle.n**2)
                self.assertEqual(len(puzzle.clues), puzzle.n**2)
                self.assertIn(CellId(0, 0), puzzle.initial_revealed)
                self.assertEqual(
                    {type(clue) for clue in puzzle.clues.values()},
                    {Count, Different, Compare, Parity},
                )
                self.assertEqual(
                    {
                        clue.op
                        for clue in puzzle.clues.values()
                        if isinstance(clue, Count)
                    },
                    {Count.EQ, Count.GE, Count.LE},
                )
                self.assertEqual(
                    sum(
                        isinstance(clue, (Parity, Compare))
                        for clue in puzzle.clues.values()
                    ),
                    3,
                )
                if puzzle.n == 5:
                    self.assertEqual(
                        max(len(clue.cells(puzzle.n)) for clue in puzzle.clues.values()),
                        25,
                    )

    @unittest.skipIf(
        not SEMANTICS_AVAILABLE,
        "waiting for griductive.logic.semantics to be merged into dev",
    )
    def test_each_puzzle_has_exactly_one_model_by_semantics(self) -> None:
        assert holds is not None
        for path in BRUTE_FORCE_PUZZLES:
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

    def test_m5_checks_uniqueness_for_all_valid_puzzles(self) -> None:
        for path in SAMPLE_PUZZLES:
            with self.subTest(path=path.name):
                puzzle = load_puzzle(path)
                report = check_uniqueness(tuple(puzzle.clues.values()), n=puzzle.n)
                self.assertEqual(report.status, "UNIQUE")
                self.assertEqual(report.models_found, 1)
                self.assertEqual(report.models[0], puzzle.solution)
                self.assertGreater(report.stats.decisions, 0)
                self.assertGreaterEqual(report.stats.backtracks, 1)

    def test_experiment_runner_records_unique_and_dpll_metrics(self) -> None:
        for path in SAMPLE_PUZZLES:
            with self.subTest(path=path.name):
                row, trace = run_puzzle(path)
                self.assertEqual(trace.terminal, "SOLVED")
                self.assertEqual(row["unique"], "UNIQUE")
                self.assertEqual(row["unique_models_found"], 1)
                self.assertGreater(row["decisions"], 0)
                self.assertGreater(row["backtracks"], 0)
                self.assertGreater(row["unique_decisions"], 0)
                self.assertGreater(row["unique_backtracks"], 0)
                self.assertGreater(row["sat_calls"], 0)
                self.assertEqual(row["unique_models_found"], 1)

    def test_game_engine_submit_uses_real_logic_agent_classify(self) -> None:
        for path in CLASSIFIABLE_PUZZLES:
            with self.subTest(path=path.name):
                agent = LogicAgent()
                engine = GameEngine.load(str(path), agent.classify)
                initially_revealed = len(engine.public_state().revealed_clues)
                if engine.n == 5:
                    initially_revealed_cells = engine.puzzle.initial_revealed
                    revealed_rows = {cell.row for cell in initially_revealed_cells}
                    self.assertEqual(initially_revealed, 1)
                    self.assertLess(len(revealed_rows), engine.n)
                steps = 0
                while not engine.is_solved():
                    state = engine.public_state()
                    forced = None
                    for candidate in state.unsolved:
                        classification = agent.classify(state, candidate)
                        if classification.verdict.name in ("CRIMINAL", "INNOCENT"):
                            forced = (candidate, classification)
                            break
                    self.assertIsNotNone(
                        forced, f"no forced cell remains in {path.name}"
                    )
                    cell, classification = forced
                    self.assertIn(
                        classification.verdict.name,
                        ("CRIMINAL", "INNOCENT"),
                        f"no forced cell remains in {path.name}",
                    )
                    submitted = (
                        Status.CRIMINAL
                        if classification.verdict.name == "CRIMINAL"
                        else Status.INNOCENT
                    )
                    result = engine.submit(cell, submitted)
                    self.assertIs(result.outcome, VerdictOutcome.ACCEPTED)
                    self.assertTrue(result.queries)
                    steps += 1
                self.assertEqual(engine.public_state().proved, engine.puzzle.solution)
                self.assertEqual(
                    steps, engine.n**2 - len(engine.puzzle.initial_revealed)
                )
                if engine.n == 5:
                    self.assertGreaterEqual(steps, 20)

    def test_invalid_puzzle_fixtures_are_rejected_by_loader(self) -> None:
        invalid_puzzles = (
            "bad_invalid_k.json",
            "bad_missing_cell.json",
            "bad_unknown_cell.json",
            "bad_schema.json",
            "bad_solution_mismatch.json",
        )
        for filename in invalid_puzzles:
            with self.subTest(filename=filename), self.assertRaises(PuzzleError):
                load_puzzle(ROOT / "puzzles" / filename)

        with self.assertRaisesRegex(PuzzleError, r"\$\.clues\.B1"):
            load_puzzle(ROOT / "puzzles/bad_contradiction.json")

    def test_m5_distinguishes_not_unique_and_stuck_puzzles(self) -> None:
        not_unique = load_puzzle(ROOT / "puzzles/bad_not_unique.json")
        not_unique_report = check_uniqueness(
            tuple(not_unique.clues.values()), n=not_unique.n
        )
        self.assertEqual(not_unique_report.status, "NOT_UNIQUE")
        self.assertEqual(not_unique_report.models_found, 2)

        stuck = load_puzzle(ROOT / "puzzles/bad_stuck.json")
        stuck_report = check_uniqueness(tuple(stuck.clues.values()), n=stuck.n)
        self.assertEqual(stuck_report.status, "UNIQUE")
        agent = LogicAgent()
        engine = GameEngine(stuck, agent.classify)
        self.assertIsNone(agent.next_forced(engine.public_state()))


if __name__ == "__main__":
    unittest.main()
