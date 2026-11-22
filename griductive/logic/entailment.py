"""Logical entailment classification for a single grid cell using DPLL."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import time

from griductive.logic.dpll import DPLLSolver, SolverStats, SolverTimeout
from griductive.logic.encoder import KB
from griductive.logic.varmap import VarMap
from griductive.model.cell import CellId


class Verdict(Enum):
    """Entailment verdict for a cell under a knowledge base."""

    CRIMINAL = "CRIMINAL"
    INNOCENT = "INNOCENT"
    UNKNOWN = "UNKNOWN"
    INCONSISTENT = "INCONSISTENT"


@dataclass(frozen=True)
class SatQueryRecord:
    """Record of a single SAT solver call made during entailment checking."""

    cell: CellId | None
    assumption: int | None
    satisfiable: bool
    stats: SolverStats


@dataclass(frozen=True)
class Classification:
    """Classification result containing the verdict and SAT query history."""

    verdict: Verdict
    queries: tuple[SatQueryRecord, ...]


def check_kb_consistency(
    kb: KB,
    solver: DPLLSolver | None = None,
    timeout: float | None = None,
) -> SatQueryRecord:
    """Execute an assumption-free SAT(KB) check to verify KB consistency."""
    active_solver = solver if solver is not None else DPLLSolver()
    res = active_solver.solve(
        clauses=kb.clauses,
        num_vars=kb.num_vars,
        assumptions=(),
        timeout=timeout,
    )
    return SatQueryRecord(
        cell=None,
        assumption=None,
        satisfiable=res.satisfiable,
        stats=res.stats,
    )


def classify(
    kb: KB,
    varmap: VarMap,
    cell: CellId,
    solver: DPLLSolver | None = None,
    timeout: float | None = None,
) -> Classification:
    """Determine the entailed status of ``cell`` from ``kb`` via refutation."""
    if not isinstance(kb, KB):
        raise TypeError("kb must be a KB instance")
    if not isinstance(varmap, VarMap):
        raise TypeError("varmap must be a VarMap instance")
    if kb.n_primary != varmap.n_primary:
        raise ValueError(
            f"kb.n_primary ({kb.n_primary}) does not match varmap.n_primary ({varmap.n_primary})"
        )

    var = varmap.var(cell)
    active_solver = solver if solver is not None else DPLLSolver()
    deadline = (time.perf_counter() + timeout) if timeout is not None else None

    def _remaining() -> float | None:
        if deadline is None:
            return None
        return deadline - time.perf_counter()

    # Query 1: SAT(KB ^ ~C_i) -> test if cell can be INNOCENT (-var)
    res_neg = active_solver.solve(
        clauses=kb.clauses,
        num_vars=kb.num_vars,
        assumptions=(-var,),
        timeout=_remaining(),
    )
    q_neg = SatQueryRecord(
        cell=cell,
        assumption=-var,
        satisfiable=res_neg.satisfiable,
        stats=res_neg.stats,
    )

    # Query 2: SAT(KB ^ C_i) -> test if cell can be CRIMINAL (+var)
    try:
        res_pos = active_solver.solve(
            clauses=kb.clauses,
            num_vars=kb.num_vars,
            assumptions=(var,),
            timeout=_remaining(),
        )
    except SolverTimeout as exc:
        combined = SolverStats()
        combined.add(q_neg.stats)
        if exc.stats is not None:
            combined.add(exc.stats)
        exc.stats = combined
        raise

    q_pos = SatQueryRecord(
        cell=cell,
        assumption=var,
        satisfiable=res_pos.satisfiable,
        stats=res_pos.stats,
    )

    queries = (q_neg, q_pos)

    if not res_neg.satisfiable and not res_pos.satisfiable:
        verdict = Verdict.INCONSISTENT
    elif not res_neg.satisfiable and res_pos.satisfiable:
        verdict = Verdict.CRIMINAL
    elif res_neg.satisfiable and not res_pos.satisfiable:
        verdict = Verdict.INNOCENT
    else:
        verdict = Verdict.UNKNOWN

    return Classification(verdict=verdict, queries=queries)