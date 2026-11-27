"""Unit tests for Tkinter GUI instantiation and basic interaction."""

import unittest
from pathlib import Path
try:
    import tkinter as tk
except (ImportError, ModuleNotFoundError) as error:
    tk = None
    TKINTER_IMPORT_ERROR = error
else:
    TKINTER_IMPORT_ERROR = None


from griductive.engine.dummy_engine import DummyEngine, VerdictOutcome, VerdictResult
from griductive.model.cell import CellId, Status


@unittest.skipIf(TKINTER_IMPORT_ERROR is not None, "Tkinter is unavailable")
class GUITests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            from griductive.gui.app import GriductiveGUI
            self.GriductiveGUI = GriductiveGUI
            self.root = tk.Tk()
            self.root.withdraw()  # Hide root window during testing
        except Exception as e:
            self.skipTest(f"Tkinter environment not available for testing: {e}")

    def tearDown(self) -> None:
        if hasattr(self, "root") and self.root is not None:
            self.root.destroy()

    def test_gui_initialization_with_dummy_engine(self) -> None:
        engine = DummyEngine()
        gui = self.GriductiveGUI(self.root, engine)
        self.assertEqual(gui.engine.n, 3)
        self.assertIn(CellId(0, 0), engine.public_state().proved)
        self.assertEqual(gui.cards[CellId(0, 0)]["name_label"].cget("text"), "Alice")
        self.assertEqual(gui.cards[CellId(0, 0)]["coord_label"].cget("text"), "A1")

    def test_gui_restart(self) -> None:
        engine = DummyEngine()
        gui = self.GriductiveGUI(self.root, engine)
        gui.on_restart()
        self.assertEqual(len(engine.public_state().proved), 1)

    def test_gui_verdict_outcomes(self) -> None:
        engine = DummyEngine()
        gui = self.GriductiveGUI(self.root, engine)
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
        gui = self.GriductiveGUI(self.root, engine)
        state = engine.public_state()
        self.assertTrue(len(state.revealed_clues) > 0)

        # Select first clue in the wrapped text panel
        gui._selected_clue_index = 0
        gui.on_clue_selected()

        first_clue = state.revealed_clues[0]
        expected_cells = set(first_clue.cells(state.n))
        self.assertEqual(gui.highlighted_cells, expected_cells)

    def test_compare_highlight_uses_two_regions(self) -> None:
        from griductive.engine.game_engine import GameEngine
        from griductive.logic.agent import LogicAgent

        path = Path(__file__).resolve().parents[1] / "puzzles" / "3x3_01.json"
        engine = GameEngine.load(str(path), LogicAgent().classify)
        gui = self.GriductiveGUI(self.root, engine)
        gui._selected_clue_index = 0
        gui.on_clue_selected()
        clue = engine.public_state().revealed_clues[0]
        self.assertEqual(gui.highlighted_left, set(clue.left_cells(engine.n)))
        self.assertEqual(gui.highlighted_right, set(clue.right_cells(engine.n)))
        self.assertEqual(gui.clue_listbox.cget("wrap"), tk.WORD)

    def test_real_m2_puzzle_displays_all_clue_families(self) -> None:
        from griductive.engine.game_engine import GameEngine
        from griductive.logic.agent import LogicAgent
        from griductive.orchestration.runner_loop import deduction_loop
        from griductive.logic.trace import TraceLog

        path = Path(__file__).resolve().parents[1] / "puzzles" / "3x3_01.json"
        agent = LogicAgent()
        engine = GameEngine.load(str(path), agent.classify)
        gui = self.GriductiveGUI(self.root, engine)
        trace = TraceLog()
        list(deduction_loop(engine, agent, trace))
        gui.refresh()
        rendered = gui.clue_listbox.get("1.0", tk.END).lower()
        for family in ("có đúng", "có ít nhất", "có nhiều nhất", "số chẵn", "nhiều hơn"):
            self.assertIn(family, rendered)
        self.assertNotIn("clue@", rendered)

    def test_gui_displays_human_clue_text_when_available(self) -> None:
        from griductive.engine.game_engine import GameEngine
        from griductive.logic.agent import LogicAgent

        path = Path(__file__).resolve().parents[1] / "puzzles" / "bad_stuck.json"
        engine = GameEngine.load(str(path), LogicAgent().classify)
        gui = self.GriductiveGUI(self.root, engine)
        rendered = gui.clue_listbox.get("1.0", tk.END)
        self.assertIn(
            "Alice: Trong hàng thứ hai, chỉ có một người là tội phạm.",
            rendered,
        )
        self.assertNotIn("clue@", rendered)

    def test_loading_puzzle_clears_selection_and_updates_title(self) -> None:
        from griductive.engine.game_engine import GameEngine
        from griductive.logic.agent import LogicAgent

        gui = self.GriductiveGUI(self.root, DummyEngine())
        puzzle_dir = Path(__file__).resolve().parents[1] / "puzzles"
        for size in (3, 4, 5, 3):
            gui.selected_cell = CellId(1, 1)
            gui._selected_clue_index = 0
            path = puzzle_dir / f"{size}x{size}_01.json"
            gui._load_real_puzzle(str(path))
            self.assertIsNone(gui.selected_cell)
            self.assertIsNone(gui._selected_clue_index)
            self.assertIn(path.name, self.root.title())
            self.assertIn(f"{size}×{size}", self.root.title())
            self.assertEqual(gui.engine.n, size)
            for row in range(1, size + 1):
                # No forced minimum height: rows share the available space.
                self.assertEqual(gui.grid_frame.grid_rowconfigure(row, "minsize"), 0)
            self.root.update_idletasks()
            if size >= 5:
                # Compact cards: the whole 5x5 grid must stay well within a
                # 760px-high window (header/footer/panel chrome take ~200px).
                self.assertLessEqual(gui.grid_frame.winfo_reqheight(), 560)
            if size == 3 and gui._grid_dimension == 3:
                for track in (4, 5):
                    self.assertEqual(gui.grid_frame.grid_rowconfigure(track, "weight"), 0)
                    self.assertIn(gui.grid_frame.grid_rowconfigure(track, "uniform"), (None, ""))
                    self.assertEqual(gui.grid_frame.grid_columnconfigure(track, "weight"), 0)
                    self.assertIn(gui.grid_frame.grid_columnconfigure(track, "uniform"), (None, ""))
            bottom_right = CellId(size - 1, size - 1)
            character = gui.engine.puzzle.characters[bottom_right]
            self.assertEqual(
                gui.cards[bottom_right]["name_label"].cget("text"), character.name
            )
            self.assertEqual(
                gui.cards[bottom_right]["job_label"].cget("text"), character.job
            )
            self.assertEqual(
                gui.cards[bottom_right]["coord_label"].cget("text"),
                str(bottom_right),
            )
            if size == 5:
                self.assertEqual(gui.cards[bottom_right]["frame"].grid_info()["padx"], 2)
                self.assertEqual(gui.cards[bottom_right]["frame"].grid_info()["pady"], 2)


if __name__ == "__main__":
    unittest.main()