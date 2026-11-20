"""Deduction trace records and JSON/CSV serialization."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass, field
from typing import Literal

from griductive.logic.entailment import SatQueryRecord
from griductive.model.cell import CellId, Status


@dataclass(frozen=True)
class TraceStep:
    """One accepted deduction and the SAT queries that justified it."""

    step: int
    active_clue_ids: tuple[str, ...]
    sat_queries: tuple[SatQueryRecord, ...]
    verdict: tuple[CellId, Status]
    revealed_clue_id: str | None


@dataclass
class TraceLog:
    """Complete deduction run, suitable for saving as JSON or CSV."""

    steps: list[TraceStep] = field(default_factory=list)
    terminal: Literal["SOLVED", "STUCK", "INCONSISTENT", "TIMEOUT", "ERROR"] = "STUCK"
    error: str = ""

    def to_json(self) -> str:
        """Serialize the trace with stable field ordering and readable IDs."""
        return json.dumps(
            {"terminal": self.terminal, "error": self.error,
             "steps": [_step_dict(step) for step in self.steps]},
            ensure_ascii=False, indent=2,
        )

    def to_csv(self) -> str:
        """Serialize one deduction step per CSV row; query records are JSON cells."""
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=(
            "step", "active_clue_ids", "sat_queries", "cell", "status",
            "revealed_clue_id", "terminal",
        ))
        writer.writeheader()
        for step in self.steps:
            writer.writerow({
                "step": step.step,
                "active_clue_ids": json.dumps(step.active_clue_ids),
                "sat_queries": json.dumps([_query_dict(q) for q in step.sat_queries]),
                "cell": str(step.verdict[0]), "status": step.verdict[1].value,
                "revealed_clue_id": step.revealed_clue_id or "",
                "terminal": self.terminal,
            })
        if not self.steps:
            writer.writerow({"terminal": self.terminal})
        return output.getvalue()


def _query_dict(query: SatQueryRecord) -> dict[str, object]:
    return {
        "cell": str(query.cell) if query.cell is not None else None,
        "assumption": query.assumption, "satisfiable": query.satisfiable,
        "stats": asdict(query.stats),
    }


def _step_dict(step: TraceStep) -> dict[str, object]:
    return {
        "step": step.step, "active_clue_ids": list(step.active_clue_ids),
        "sat_queries": [_query_dict(query) for query in step.sat_queries],
        "cell": str(step.verdict[0]), "status": step.verdict[1].value,
        "revealed_clue_id": step.revealed_clue_id,
    }
