"""Run puzzle suites and export aggregate deduction metrics as CSV."""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path
from typing import Any, Literal

from griductive.engine.game_engine import GameEngine
from griductive.io.loader import load_puzzle
from griductive.logic.agent import LogicAgent
from griductive.logic.encoder import CNFEncoder
from griductive.logic.trace import TraceLog
from griductive.logic.uniqueness import check_uniqueness
from griductive.orchestration.runner_loop import deduction_loop


Encoding = Literal["combinatorial", "sequential"]
CSV_FIELDS = (
    "puzzle", "size", "encoding", "primary_vars", "aux_vars", "clauses",
    "clauses_peak", "sat_calls", "decisions", "propagations", "backtracks",
    "steps", "waves", "runtime_s", "unique", "unique_runtime_s", "status",
    "error", "trial",
)


def _base_row(name: str, encoding: Encoding, started: float) -> dict[str, Any]:
    return {
        "puzzle": name, "size": "N/A", "encoding": encoding,
        "primary_vars": "", "aux_vars": "", "clauses": "",
        "clauses_peak": "", "sat_calls": 0, "decisions": 0,
        "propagations": 0, "backtracks": 0, "steps": 0, "waves": 0,
        "runtime_s": round(time.perf_counter() - started, 6), "unique": "",
        "unique_runtime_s": "", "status": "ERROR", "error": "", "trial": 1,
    }


def run_puzzle(
    path: str | Path,
    timeout: float | None = 60.0,
    encoding: Encoding = "combinatorial",
) -> tuple[dict[str, Any], TraceLog]:
    """Run deduction through the shared loop and report uniqueness separately."""
    if encoding not in ("combinatorial", "sequential"):
        raise ValueError("encoding must be 'combinatorial' or 'sequential'")
    puzzle_path = Path(path)
    started = time.perf_counter()
    row = _base_row(puzzle_path.name, encoding, started)
    trace = TraceLog(terminal="ERROR")
    try:
        puzzle = load_puzzle(puzzle_path)
    except Exception as exc:
        trace.error = f"{type(exc).__name__}: {exc}"
        row.update(error=trace.error, runtime_s=round(time.perf_counter() - started, 6))
        return row, trace

    encoder_factory = lambda n: CNFEncoder(n, encoding=encoding)
    agent = LogicAgent(encoder_factory=encoder_factory)
    engine = GameEngine(puzzle, agent.classify)
    trace = TraceLog(terminal="STUCK")
    loop = iter(deduction_loop(engine, agent, trace, timeout=timeout))
    clauses_peak = 0
    loop_runtime = 0.0
    while True:
        tick = time.perf_counter()
        try:
            next(loop)
        except StopIteration:
            loop_runtime += time.perf_counter() - tick
            break
        loop_runtime += time.perf_counter() - tick
        try:
            current_kb = encoder_factory(puzzle.n).build_kb(engine.public_state())
            clauses_peak = max(clauses_peak, current_kb.n_clauses)
        except Exception:
            pass

    unique_started = time.perf_counter()
    try:
        uniqueness = check_uniqueness(
            tuple(puzzle.clues.values()),
            n=puzzle.n,
            encoder=CNFEncoder(puzzle.n, encoding=encoding),
        )
        unique = uniqueness.status
    except Exception as exc:
        unique = "ERROR"
        if not trace.error:
            trace.error = f"uniqueness {type(exc).__name__}: {exc}"
    unique_runtime = round(time.perf_counter() - unique_started, 6)

    try:
        kb = CNFEncoder(puzzle.n, encoding=encoding).build_kb(engine.public_state())
        primary_vars, aux_vars, clauses = kb.n_primary, kb.n_aux, kb.n_clauses
        clauses_peak = max(clauses_peak, clauses)
    except Exception:
        primary_vars, aux_vars, clauses = puzzle.n * puzzle.n, 0, 0
    row.update(
        size=puzzle.n,
        primary_vars=primary_vars,
        aux_vars=aux_vars,
        clauses=clauses,
        clauses_peak=clauses_peak,
        sat_calls=trace.sat_calls,
        decisions=trace.stats.decisions,
        propagations=trace.stats.propagations,
        backtracks=trace.stats.backtracks,
        steps=len(trace.steps),
        waves=trace.waves,
        runtime_s=round(loop_runtime, 6),
        unique=unique,
        unique_runtime_s=unique_runtime,
        status=trace.terminal,
        error=trace.error,
    )
    return row, trace


def run_suite(
    suite: str | Path,
    output: str | Path | None = None,
    timeout: float | None = 60.0,
    name_filter: str | None = None,
    encoding: Encoding = "combinatorial",
) -> list[dict[str, Any]]:
    """Run sorted ``*.json`` puzzles, preserve failures, optionally write CSV."""
    suite_path = Path(suite)
    paths = sorted(suite_path.glob("*.json"), key=lambda item: item.name)
    if name_filter:
        paths = [path for path in paths if name_filter.lower() in path.name.lower()]
    rows = [run_puzzle(path, timeout, encoding)[0] for path in paths]
    if output is not None:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    return rows


def main() -> None:
    """Command-line entry point: ``python -m griductive.experiments.runner``."""
    parser = argparse.ArgumentParser(description="Run Griductive puzzle experiments")
    parser.add_argument("--suite", default="puzzles/")
    parser.add_argument("--out", default="results/experiment.csv")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--filter", dest="name_filter")
    parser.add_argument(
        "--encoding", choices=("combinatorial", "sequential"),
        default="combinatorial",
    )
    args = parser.parse_args()
    rows = run_suite(args.suite, args.out, args.timeout, args.name_filter, args.encoding)
    print(f"Wrote {len(rows)} puzzle result(s) to {args.out}")


if __name__ == "__main__":
    main()
