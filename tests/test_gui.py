"""Unit tests for Tkinter GUI instantiation and basic interaction."""

import unittest
import tkinter as tk

from griductive.engine.dummy_engine import DummyEngine, VerdictOutcome, VerdictResult
from griductive.gui.app import GriductiveGUI
from griductive.model.cell import CellId, Status


class GUITests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
            self.root.withdraw()  # Hide root window during testing
        except Exception as e:
            self.skipTest(f"Tkinter environment not available for testing: {e}")

    def tearDown(self) -> None:
        if hasattr(self, "root") and self.root is not None:
            self.root.destroy()

    def test_gui_initialization_with_dummy_engine(self) -> None:
        engine = DummyEngine()
        gui = GriductiveGUI(self.root, engine)
        self.assertEqual(gui.engine.n, 3)
        self.assertIn(CellId(0, 0), engine.public_state().proved)

    def test_gui_restart(self) -> None:
        engine = DummyEngine()
        gui = GriductiveGUI(self.root, engine)
        gui.on_restart()
        self.assertEqual(len(engine.public_state().proved), 1)

    def test_gui_verdict_outcomes(self) -> None:
        engine = DummyEngine()
        gui = GriductiveGUI(self.root, engine)
        cell = CellId(0, 1)

        # Test NOT_PROVABLE handling
        res_np = VerdictResult(outcome=VerdictOutcome.NOT_PROVABLE, cell=cell)
        gui._handle_verdict_result(cell, Status.CRIMINAL, res_np)
        self.assertIn("NOT_PROVABLE", gui.lbl_status.cget("text"))

        # Test CONTRADICTED handling
        res_c = VerdictResult(outcome=VerdictOutcome.CONTRADICTED, cell=cell)
        gui._handle_verdict_result(cell, Status.INNOCENT, res_c)
        self.assertIn("CONTRADICTED", gui.lbl_status.cget("text"))

    def test_gui_clue_highlight(self) -> None:
        engine = DummyEngine()
        gui = GriductiveGUI(self.root, engine)
        state = engine.public_state()
        self.assertTrue(len(state.revealed_clues) > 0)

        # Select first clue in listbox
        gui.clue_listbox.selection_set(0)
        gui.on_clue_selected()

        first_clue = state.revealed_clues[0]
        expected_cells = set(first_clue.cells(state.n))
        self.assertEqual(gui.highlighted_cells, expected_cells)


if __name__ == "__main__":
    unittest.main()
