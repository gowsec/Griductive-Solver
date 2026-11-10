"""Unit tests for DummyEngine and GameEngine."""

import unittest

from griductive.engine.dummy_engine import DummyEngine, VerdictOutcome
from griductive.engine.game_engine import GameEngine
from griductive.model.cell import CellId, Status


class DummyEngineTests(unittest.TestCase):
    def test_dummy_engine_initialization(self) -> None:
        engine = DummyEngine()
        self.assertEqual(engine.n, 3)
        state = engine.public_state()
        self.assertEqual(state.n, 3)
        # 1 cell initially proved (A1)
        self.assertEqual(len(state.proved), 1)
        self.assertIn(CellId(0, 0), state.proved)
        self.assertEqual(len(state.unsolved), 8)

    def test_submit_correct_verdict_accepted(self) -> None:
        engine = DummyEngine()
        # Cell B1 (0, 1) is INNOCENT in default dummy solution
        res = engine.submit(CellId(0, 1), Status.INNOCENT)
        self.assertEqual(res.outcome, VerdictOutcome.ACCEPTED)
        self.assertIsNotNone(res.revealed_clue)

        state = engine.public_state()
        self.assertIn(CellId(0, 1), state.proved)
        self.assertEqual(len(state.unsolved), 7)

    def test_submit_wrong_verdict_contradicted(self) -> None:
        engine = DummyEngine()
        # Cell B1 (0, 1) is INNOCENT, so submitting CRIMINAL should be CONTRADICTED
        res = engine.submit(CellId(0, 1), Status.CRIMINAL)
        self.assertEqual(res.outcome, VerdictOutcome.CONTRADICTED)
        self.assertIsNone(res.revealed_clue)

        # Game state should be unchanged
        state = engine.public_state()
        self.assertNotIn(CellId(0, 1), state.proved)
        self.assertEqual(len(state.unsolved), 8)

    def test_restart(self) -> None:
        engine = DummyEngine()
        engine.submit(CellId(0, 1), Status.INNOCENT)
        self.assertEqual(len(engine.public_state().proved), 2)
        engine.restart()
        self.assertEqual(len(engine.public_state().proved), 1)


if __name__ == "__main__":
    unittest.main()
