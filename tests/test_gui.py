"""Unit tests for Tkinter GUI instantiation and basic interaction."""

import unittest
import tkinter as tk

from griductive.engine.dummy_engine import DummyEngine
from griductive.gui.app import GriductiveGUI
from griductive.model.cell import CellId


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


if __name__ == "__main__":
    unittest.main()
