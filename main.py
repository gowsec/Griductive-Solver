"""Griductive Solver Entry Point."""

from __future__ import annotations

import argparse
import tkinter as tk

from griductive.engine.game_engine import GameEngine
from griductive.gui.app import GriductiveGUI
from griductive.logic.agent import LogicAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="Griductive Solver")
    parser.add_argument("--gui", action="store_true", default=True,
                        help="Run Tkinter Graphical User Interface (default)")
    parser.add_argument("--puzzle", type=str, default=None,
                        help="Path to puzzle JSON file")
    args = parser.parse_args()

    root = tk.Tk()
    if args.puzzle:
        agent = LogicAgent()
        engine = GameEngine.load(args.puzzle, agent.classify)
    else:
        engine = None
    GriductiveGUI(root, engine)
    root.mainloop()


if __name__ == "__main__":
    main()
