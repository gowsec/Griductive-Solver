"""Griductive Solver Entry Point."""

from __future__ import annotations

import argparse
import sys
import tkinter as tk

from griductive.engine.dummy_engine import DummyEngine
from griductive.gui.app import GriductiveGUI


def main() -> None:
    parser = argparse.ArgumentParser(description="Griductive Solver")
    parser.add_argument(
        "--gui",
        action="store_true",
        default=True,
        help="Run Tkinter Graphical User Interface (default)",
    )
    parser.add_argument(
        "--puzzle",
        type=str,
        default=None,
        help="Path to puzzle JSON file",
    )

    args = parser.parse_args()

    root = tk.Tk()
    engine = DummyEngine()
    app = GriductiveGUI(root, engine)

    if args.puzzle:
        app.log(f"Loading specified puzzle: {args.puzzle}")

    root.mainloop()


if __name__ == "__main__":
    main()

