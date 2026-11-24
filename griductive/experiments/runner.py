"""Run puzzle suites and export aggregate deduction metrics as CSV."""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path
from typing import Any

from griductive.engine.game_engine import GameEngine
from griductive.io.loader import load_puzzle
from griductive.logic.agent import LogicAgent
from griductive.logic.dpll import SolverTimeout
from griductive.logic.encoder import CNFEncoder
from griductive.logic.entailment import Verdict
from griductive.logic.trace import TraceLog, TraceStep
from griductive.logic.uniqueness import check_uniqueness
from griductive.model.cell import Status


CSV_FIELDS = (
    "puzzle", "size", "encoding", "primary_vars", "aux_vars", "clauses",
    "clauses_peak", "sat_calls", "decisions", "propagations", "backtracks",
    "steps", "waves", "runtime_s", "unique", "unique_models_found",
    "unique_decisions", "unique_backtracks", "unique_runtime_s", "trial",
    "status", "error",
)


def run_puzzle(path: str | Path, timeout: float | None = 60.0) -> tuple[dict[str, Any], TraceLog]:
    """Run deterministic forced deductions for one JSON puzzle.

    Timeout is a wall-clock limit checked between deductions. DPLL-level timeout
    can additionally be configured on its solver; partial counters are retained.
    """
    puzzle_path = Path(path)
    started = time.perf_counter()
    try:
        puzzle = load_puzzle(puzzle_path)
    except Exception as exc:
        trace = TraceLog(terminal="ERROR", error=f"{type(exc).__name__}: {exc}")
        return ({
            "puzzle": puzzle_path.name, "size": "", "encoding": "combinatorial",
            "primary_vars": "", "aux_vars": "", "clauses": "", "clauses_peak": "",
            "sat_calls": 0, "decisions": 0, "propagations": 0, "backtracks": 0,
            "steps": 0, "waves": 0, "runtime_s": round(time.perf_counter() - started, 6),
            "unique": "", "unique_models_found": 0, "unique_decisions": 0,
            "unique_backtracks": 0, "unique_runtime_s": 0.0, "trial": 1,
            "status": "ERROR", "error": trace.error,
        }, trace)
    agent = LogicAgent()
    engine = GameEngine(puzzle, agent.classify)
    trace = TraceLog(terminal="STUCK")
    totals = {"sat_calls": 0, "decisions": 0, "propagations": 0, "backtracks": 0}
    clauses_peak = 0

    unique_started = time.perf_counter()
    try:
        unique_report = check_uniqueness(tuple(puzzle.clues.values()), n=puzzle.n)
        unique_status = unique_report.status
        unique_models_found = unique_report.models_found
        unique_decisions = unique_report.stats.decisions
        unique_backtracks = unique_report.stats.backtracks
        totals["sat_calls"] += 2 if unique_status != "UNSAT" else 1
        totals["decisions"] += unique_decisions
        totals["propagations"] += unique_report.stats.propagations
        totals["backtracks"] += unique_backtracks
    except Exception as exc:
        unique_status = "ERROR"
        unique_models_found = 0
        unique_decisions = 0
        unique_backtracks = 0
        unique_error = f"uniqueness: {type(exc).__name__}: {exc}"
    else:
        unique_error = ""
    unique_runtime = time.perf_counter() - unique_started

    try:
        while not engine.is_solved():
            if timeout is not None and time.perf_counter() - started >= timeout:
                trace.terminal = "TIMEOUT"
                break
            state = engine.public_state()
            try:
                state_kb = CNFEncoder(puzzle.n).build_kb(state)
                clauses_peak = max(clauses_peak, state_kb.n_clauses)
            except Exception:
                pass
            forced = agent.next_forced(state)
            queries = agent.last_queries
            _add_queries(totals, queries)
            if agent.last_verdict is Verdict.INCONSISTENT:
                trace.terminal = "INCONSISTENT"
                break
            if forced is None:
                trace.terminal = "STUCK"
                break
            cell, verdict = forced
            status = Status.CRIMINAL if verdict is Verdict.CRIMINAL else Status.INNOCENT
            result = engine.submit(cell, status)
            _add_queries(totals, tuple(getattr(result, "queries", ())))
            if result.outcome.name != "ACCEPTED":
                trace.terminal = "INCONSISTENT" if result.outcome.name == "INCONSISTENT" else "ERROR"
                trace.error = f"forced verdict rejected by engine: {result.outcome.name}"
                break
            trace.steps.append(TraceStep(
                len(trace.steps) + 1,
                tuple(clue.id for clue in state.revealed_clues), queries,
                (cell, status), result.revealed_clue.id if result.revealed_clue else None,
            ))
        else:
            trace.terminal = "SOLVED"
    except SolverTimeout as exc:
        trace.terminal, trace.error = "TIMEOUT", str(exc)
    except Exception as exc:
        trace.terminal, trace.error = "ERROR", f"{type(exc).__name__}: {exc}"

    try:
        kb = CNFEncoder(puzzle.n).build_kb(engine.public_state())
        primary_vars, aux_vars, clauses = kb.n_primary, kb.n_aux, kb.n_clauses
        clauses_peak = max(clauses_peak, clauses)
    except Exception:
        primary_vars, aux_vars, clauses = puzzle.n * puzzle.n, 0, 0

    if unique_error and not trace.error:
        trace.error = unique_error
    row = {
        "puzzle": puzzle_path.name, "size": puzzle.n, "encoding": "combinatorial",
        "primary_vars": primary_vars, "aux_vars": aux_vars, "clauses": clauses,
        "clauses_peak": clauses_peak,
        **totals, "steps": len(trace.steps), "waves": len(trace.steps),
        "runtime_s": round(time.perf_counter() - started - unique_runtime, 6),
        "unique": unique_status, "unique_models_found": unique_models_found,
        "unique_decisions": unique_decisions,
        "unique_backtracks": unique_backtracks,
        "unique_runtime_s": round(unique_runtime, 6), "trial": 1,
        "status": trace.terminal, "error": trace.error,
    }
    return row, trace


def run_suite(
    suite: str | Path, output: str | Path | None = None, timeout: float | None = 60.0,
    name_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Run sorted ``*.json`` puzzles, preserve failures, optionally write CSV."""
    suite_path = Path(suite)
    paths = sorted(suite_path.glob("*.json"), key=lambda item: item.name)
    if name_filter:
        paths = [path for path in paths if name_filter.lower() in path.name.lower()]
    rows = [run_puzzle(path, timeout)[0] for path in paths]
    if output is not None:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    return rows


def _add_queries(totals: dict[str, int], queries: tuple[object, ...]) -> None:
    totals["sat_calls"] += len(queries)
    for query in queries:
        stats = query.stats
        for key in ("decisions", "propagations", "backtracks"):
            totals[key] += getattr(stats, key)


def main() -> None:
    """Command-line entry point: ``python -m griductive.experiments.runner``."""
    parser = argparse.ArgumentParser(description="Run Griductive puzzle experiments")
    parser.add_argument("--suite", default="puzzles/")
    parser.add_argument("--out", default="results/experiment.csv")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--filter", dest="name_filter")
    args = parser.parse_args()
    rows = run_suite(args.suite, args.out, args.timeout, args.name_filter)
    print(f"Wrote {len(rows)} puzzle result(s) to {args.out}")


if __name__ == "__main__":
    main()
