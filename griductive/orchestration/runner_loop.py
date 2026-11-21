"""Incremental deductive solving loop shared by the GUI and experiments."""

from __future__ import annotations

from collections.abc import Iterator

from griductive.engine.game_engine import GameEngine, VerdictOutcome
from griductive.logic.agent import LogicAgent
from griductive.logic.entailment import Verdict
from griductive.logic.trace import TraceLog, TraceStep
from griductive.model.cell import Status


def deduction_loop(engine: GameEngine, agent: LogicAgent, trace: TraceLog | None = None) -> Iterator[TraceStep]:
    """Yield each accepted forced move and record the final state in ``trace``."""
    log = trace if trace is not None else TraceLog()
    log.terminal = "STUCK"
    try:
        while not engine.is_solved():
            state = engine.public_state()
            forced = agent.next_forced(state)
            queries = agent.last_queries
            if forced is None:
                log.terminal = "INCONSISTENT" if agent.last_verdict is Verdict.INCONSISTENT else "STUCK"
                return
            cell, verdict = forced
            status = Status.CRIMINAL if verdict is Verdict.CRIMINAL else Status.INNOCENT
            result = engine.submit(cell, status)
            if result.outcome is not VerdictOutcome.ACCEPTED:
                log.terminal = "INCONSISTENT" if result.outcome is VerdictOutcome.INCONSISTENT else "ERROR"
                log.error = f"forced verdict rejected by engine: {result.outcome.name}"
                return
            step = TraceStep(len(log.steps) + 1, tuple(c.id for c in state.revealed_clues),
                             queries, (cell, status), result.revealed_clue.id if result.revealed_clue else None)
            log.steps.append(step)
            if engine.is_solved():
                log.terminal = "SOLVED"
            yield step
        log.terminal = "SOLVED"
    except Exception as exc:
        log.terminal = "ERROR"
        log.error = f"{type(exc).__name__}: {exc}"
        raise


