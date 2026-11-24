"""Terminal status and timeout accounting for the shared deduction loop."""

from pathlib import Path

import pytest

from griductive.engine.game_engine import GameEngine
from griductive.io.loader import load_puzzle
from griductive.logic.agent import LogicAgent
from griductive.logic.dpll import SolveResult, SolverStats, SolverTimeout
from griductive.logic.trace import TraceLog
from griductive.orchestration.runner_loop import deduction_loop


ROOT = Path(__file__).resolve().parents[1]


def _run(filename: str, timeout: float | None = None) -> TraceLog:
    agent = LogicAgent()
    engine = GameEngine(load_puzzle(ROOT / "puzzles" / filename), agent.classify)
    trace = TraceLog()
    for _ in deduction_loop(engine, agent, trace, timeout=timeout):
        pass
    return trace


def test_deduction_loop_reports_solved_and_stuck() -> None:
    assert _run("3x3_01.json").terminal == "SOLVED"
    assert _run("bad_stuck.json").terminal == "STUCK"
    assert _run("bad_not_unique.json").terminal == "STUCK"


def test_deduction_loop_reports_wall_clock_timeout() -> None:
    trace = _run("3x3_01.json", timeout=0)
    assert trace.terminal == "TIMEOUT"
    assert trace.steps == []


def test_deduction_loop_preserves_solver_timeout_statistics() -> None:
    engine = GameEngine(load_puzzle(ROOT / "puzzles" / "3x3_01.json"), lambda *_: None)

    class TimeoutAgent:
        last_queries = ()

        def classify(self, _state, _cell, timeout=None):
            raise SolverTimeout("partial timeout", SolverStats(decisions=3, propagations=4))

    trace = TraceLog()
    list(deduction_loop(engine, TimeoutAgent(), trace))
    assert trace.terminal == "TIMEOUT"
    assert trace.stats.decisions == 3
    assert trace.stats.propagations == 4
    assert trace.sat_calls == 1


def test_agent_timeout_keeps_completed_query_and_counts_timed_out_query() -> None:
    class OneThenTimeoutSolver:
        calls = 0

        def solve(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return SolveResult(
                    satisfiable=True,
                    model={},
                    stats=SolverStats(decisions=2, propagations=5),
                )
            raise SolverTimeout(
                "second query timed out", SolverStats(decisions=1, propagations=3)
            )

    engine = GameEngine(load_puzzle(ROOT / "puzzles" / "3x3_01.json"), lambda *_: None)
    solver = OneThenTimeoutSolver()
    agent = LogicAgent(solver_factory=lambda: solver)
    with pytest.raises(SolverTimeout) as exc_info:
        agent.classify(engine.public_state(), engine.public_state().unsolved[0])
    assert exc_info.value.sat_calls == 2
    assert exc_info.value.stats is not None
    assert (exc_info.value.stats.decisions, exc_info.value.stats.propagations) == (3, 8)


def test_deduction_loop_reports_unexpected_engine_error(monkeypatch) -> None:
    agent = LogicAgent()
    engine = GameEngine(load_puzzle(ROOT / "puzzles" / "3x3_01.json"), agent.classify)

    def fail_submit(_cell, _status, timeout=None):
        raise RuntimeError("submit failed")

    monkeypatch.setattr(engine, "submit", fail_submit)
    trace = TraceLog()
    list(deduction_loop(engine, agent, trace))
    assert trace.terminal == "ERROR"
    assert "submit failed" in trace.error
