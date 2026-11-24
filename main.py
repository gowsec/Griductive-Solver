"""Griductive Solver entry point.

Subcommands::

    python main.py gui        [--puzzle PATH]
    python main.py solve      PUZZLE [--timeout S] [--trace-json F] [--trace-csv F]
    python main.py experiment [--suite DIR] [--out CSV] [--timeout S] [--filter TEXT]
                              [--encoding combinatorial|sequential]
    python main.py cli        <mọi tham số của integration_cli>
    python main.py test       [tham số của pytest]

Chạy ``python main.py`` không tham số thì mở GUI (giữ hành vi cũ).
Tkinter chỉ được import khi dùng ``gui`` nên các lệnh còn lại chạy được
trên máy không có màn hình.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2


# --------------------------------------------------------------------------- #
# gui
# --------------------------------------------------------------------------- #
def cmd_gui(args: argparse.Namespace) -> int:
    try:
        import tkinter as tk
    except ImportError:
        print("Không có tkinter. Cài python3-tk (Linux) hoặc dùng Python có Tk.", file=sys.stderr)
        return EXIT_USAGE

    from griductive.gui.app import GriductiveGUI

    if args.puzzle:
        from griductive.engine.game_engine import GameEngine
        from griductive.io.loader import PuzzleError
        from griductive.logic.agent import LogicAgent

        try:
            engine = GameEngine.load(args.puzzle, LogicAgent().classify)
        except (PuzzleError, OSError) as exc:
            print(f"LỖI puzzle: {exc}", file=sys.stderr)
            return EXIT_USAGE
    else:
        from griductive.engine.dummy_engine import DummyEngine

        engine = DummyEngine()

    root = tk.Tk()
    app = GriductiveGUI(root, engine, puzzle_path=args.puzzle)
    if args.puzzle:
        app.log(f"Loaded puzzle: {args.puzzle}")
    root.mainloop()
    return EXIT_OK


# --------------------------------------------------------------------------- #
# solve: giải một puzzle bằng vòng lặp suy diễn (không cần GUI)
# --------------------------------------------------------------------------- #
def cmd_solve(args: argparse.Namespace) -> int:
    from griductive.experiments.runner import run_puzzle

    path = Path(args.puzzle)
    if not path.is_file():
        print(f"LỖI: không thấy file {path}", file=sys.stderr)
        return EXIT_USAGE

    row, trace = run_puzzle(path, timeout=args.timeout)

    print(f"Puzzle : {row['puzzle']}  (n={row['size']})")
    for step in trace.steps:
        cell, status = step.verdict
        revealed = step.revealed_clue_id or "-"
        print(f"  bước {step.step:>2}: {cell} = {status.value:<8} -> lật {revealed}")
    print(f"Kết quả: {trace.terminal}" + (f"  ({trace.error})" if trace.error else ""))
    print(
        f"Chỉ số : sat_calls={row['sat_calls']} decisions={row['decisions']} "
        f"propagations={row['propagations']} backtracks={row['backtracks']} "
        f"runtime={row['runtime_s']}s"
    )

    if args.trace_json:
        Path(args.trace_json).write_text(trace.to_json(), encoding="utf-8")
        print(f"Đã ghi {args.trace_json}")
    if args.trace_csv:
        Path(args.trace_csv).write_text(trace.to_csv(), encoding="utf-8", newline="")
        print(f"Đã ghi {args.trace_csv}")

    return EXIT_OK if trace.terminal == "SOLVED" else EXIT_FAILED


# --------------------------------------------------------------------------- #
# experiment: chạy cả bộ puzzle, xuất CSV
# --------------------------------------------------------------------------- #
def cmd_experiment(args: argparse.Namespace) -> int:
    from griductive.experiments.runner import run_suite

    suite = Path(args.suite)
    if not suite.is_dir():
        print(f"LỖI: không thấy thư mục {suite}", file=sys.stderr)
        return EXIT_USAGE

    rows = run_suite(suite, args.out, args.timeout, args.name_filter, args.encoding)
    if not rows:
        print(f"Không có file *.json nào trong {suite} (kiểm tra puzzles/ và --filter).", file=sys.stderr)
        return EXIT_USAGE

    print(f"{'puzzle':<28}{'n':>3}{'status':>14}{'steps':>7}{'sat':>7}{'time(s)':>10}")
    for r in rows:
        print(
            f"{r['puzzle']:<28}{r['size']!s:>3}{r['status']:>14}"
            f"{r['steps']:>7}{r['sat_calls']:>7}{r['runtime_s']:>10}"
        )
    print(f"\nĐã ghi {len(rows)} dòng vào {args.out}")
    return EXIT_OK


# --------------------------------------------------------------------------- #
# cli / test: chuyển tiếp
# --------------------------------------------------------------------------- #
def cmd_cli(rest: Sequence[str]) -> int:
    from griductive.orchestration import integration_cli

    return integration_cli.main(list(rest))


def cmd_test(rest: Sequence[str]) -> int:
    try:
        import pytest
    except ImportError:
        print("Chưa cài pytest: pip install -r requirements.txt", file=sys.stderr)
        return EXIT_USAGE
    return int(pytest.main(list(rest) or ["-q"]))


# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="main.py", description="Griductive Solver")
    sub = parser.add_subparsers(dest="command")

    gui = sub.add_parser("gui", help="mở giao diện Tkinter")
    gui.add_argument("--puzzle", help="file puzzle JSON (mặc định: puzzle giả)")

    solve = sub.add_parser("solve", help="giải một puzzle bằng suy diễn, in từng bước")
    solve.add_argument("puzzle", help="file puzzle JSON")
    solve.add_argument("--timeout", type=float, default=60.0)
    solve.add_argument("--trace-json", metavar="FILE")
    solve.add_argument("--trace-csv", metavar="FILE")

    exp = sub.add_parser("experiment", help="chạy cả bộ puzzle, xuất CSV")
    exp.add_argument("--suite", default="puzzles/")
    exp.add_argument("--out", default="results/experiment.csv")
    exp.add_argument("--timeout", type=float, default=60.0)
    exp.add_argument("--filter", dest="name_filter")
    exp.add_argument(
        "--encoding", choices=("combinatorial", "sequential"),
        default="combinatorial",
    )

    sub.add_parser("cli", help="CLI tích hợp (chuyển tiếp mọi tham số)")
    sub.add_parser("test", help="chạy pytest (chuyển tiếp mọi tham số)")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # cli/test nhận tham số của chương trình khác nên không qua argparse của ta.
    if argv and argv[0] == "cli":
        return cmd_cli(argv[1:])
    if argv and argv[0] == "test":
        return cmd_test(argv[1:])
    if not argv:
        argv = ["gui"]

    args = build_parser().parse_args(argv)
    if args.command == "gui":
        return cmd_gui(args)
    if args.command == "solve":
        return cmd_solve(args)
    if args.command == "experiment":
        return cmd_experiment(args)
    build_parser().print_help()
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
