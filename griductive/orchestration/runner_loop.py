"""Incremental deductive solving loop shared by the GUI and experiments."""

from __future__ import annotations

import time
from collections.abc import Iterator

from griductive.engine.game_engine import GameEngine, VerdictOutcome
from griductive.logic.agent import LogicAgent
from griductive.logic.dpll import SolverTimeout
from griductive.logic.entailment import SatQueryRecord, Verdict
from griductive.logic.trace import TraceLog, TraceStep
from griductive.model.cell import CellId, Status


def _record_queries(trace: TraceLog, queries: tuple[SatQueryRecord, ...]) -> None:
    trace.sat_calls += len(queries)
    for query in queries:
        trace.stats.add(query.stats)


def deduction_loop(
    engine: GameEngine,
    agent: LogicAgent,
    trace: TraceLog | None = None,
    timeout: float | None = None,
) -> Iterator[TraceStep]:
    """Yield forced moves in waves and preserve partial statistics on timeout.

    Each wave classifies all unsolved cells against one frozen public state.
    It then reveals every forced result found in that state before making the
    next state snapshot. ``timeout`` is a wall-clock budget for the whole run.
    """
    log = trace if trace is not None else TraceLog()
    log.terminal = "STUCK"
    started = time.perf_counter()

    def remaining() -> float | None:
        if timeout is None:
            return None
        return timeout - (time.perf_counter() - started)

    try:
        while not engine.is_solved():
            state = engine.public_state()
            forced: list[tuple[CellId, Status]] = []
            queries_by_cell: dict[CellId, tuple[SatQueryRecord, ...]] = {}
            try:
                for cell in state.unsolved:
                    budget = remaining()
                    if budget is not None and budget <= 0:
                        log.terminal = "TIMEOUT"
                        return
                    classification = agent.classify(state, cell, timeout=budget)
                    queries_by_cell[cell] = classification.queries
                    _record_queries(log, classification.queries)
                    if classification.verdict is Verdict.INCONSISTENT:
                        log.terminal = "INCONSISTENT"
                        return
                    if classification.verdict is Verdict.CRIMINAL:
                        forced.append((cell, Status.CRIMINAL))
                    elif classification.verdict is Verdict.INNOCENT:
                        forced.append((cell, Status.INNOCENT))
            except SolverTimeout as exc:
                if exc.stats is not None:
                    log.stats.add(exc.stats)
                log.sat_calls += exc.sat_calls
                log.terminal, log.error = "TIMEOUT", str(exc)
                return

            if not forced:
                log.terminal = "STUCK"
                return

            log.waves += 1
            forced_cells = {cell for cell, _ in forced}
            unforced_queries = tuple(
                query
                for cell, queries in queries_by_cell.items()
                if cell not in forced_cells
                for query in queries
            )

            for index, (cell, status) in enumerate(forced):
                budget = remaining()
                if budget is not None and budget <= 0:
                    log.terminal = "TIMEOUT"
                    return
                try:
                    result = engine.submit(cell, status, timeout=budget)
                except SolverTimeout as exc:
                    if exc.stats is not None:
                        log.stats.add(exc.stats)
                    log.sat_calls += exc.sat_calls
                    log.terminal, log.error = "TIMEOUT", str(exc)
                    return

                submit_queries = tuple(result.queries)
                _record_queries(log, submit_queries)
                if result.outcome is not VerdictOutcome.ACCEPTED:
                    log.terminal = (
                        "INCONSISTENT"
                        if result.outcome is VerdictOutcome.INCONSISTENT
                        else "ERROR"
                    )
                    log.error = f"forced verdict rejected by engine: {result.outcome.name}"
                    return

                trace_queries = queries_by_cell[cell]
                if index == 0:
                    trace_queries = unforced_queries + trace_queries
                step = TraceStep(
                    len(log.steps) + 1,
                    tuple(clue.id for clue in state.revealed_clues),
                    trace_queries + submit_queries,
                    (cell, status),
                    result.revealed_clue.id if result.revealed_clue else None,
                )
                log.steps.append(step)
                if engine.is_solved():
                    log.terminal = "SOLVED"
                yield step

        log.terminal = "SOLVED"
    except Exception as exc:
        log.terminal = "ERROR"
        log.error = f"{type(exc).__name__}: {exc}"
