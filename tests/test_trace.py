"""Serialization coverage for deduction trace records."""

import csv
import json
from io import StringIO

from griductive.logic.agent import LogicAgent
from griductive.logic.trace import TraceLog
from griductive.engine.game_engine import GameEngine
from griductive.io.loader import load_puzzle
from griductive.orchestration.runner_loop import deduction_loop


def test_trace_serializes_solution_and_aggregate_solver_statistics() -> None:
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "puzzles" / "3x3_01.json"
    agent = LogicAgent()
    engine = GameEngine(load_puzzle(path), agent.classify)
    trace = TraceLog()
    for _ in deduction_loop(engine, agent, trace):
        pass

    document = json.loads(trace.to_json())
    assert document["terminal"] == "SOLVED"
    assert document["sat_calls"] == trace.sat_calls > 0
    assert document["stats"]["propagations"] == trace.stats.propagations
    rows = list(csv.DictReader(StringIO(trace.to_csv())))
    assert len(rows) == len(trace.steps)
    assert rows[-1]["terminal"] == "SOLVED"
