"""Logical entailment classification for a single grid cell using DPLL."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from griductive.logic.dpll import DPLLSolver, SolverStats
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
) -> SatQueryRecord:
    """Execute an assumption-free SAT(KB) check to verify KB consistency."""
    active_solver = solver if solver is not None else DPLLSolver()
    res = active_solver.solve(
        clauses=kb.clauses,
        num_vars=kb.num_vars,
        assumptions=(),
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
) -> Classification:
    """Determine the entailed status of ``cell`` from ``kb`` via refutation.

    Tests whether ``cell`` can be INNOCENT (``assumption = -v``) and whether
    it can be CRIMINAL (``assumption = +v``), where ``v = varmap.var(cell)``:
      1. Both UNSAT -> ``Verdict.INCONSISTENT`` (``KB`` itself is unsatisfiable).
      2. ``-v`` is UNSAT and ``+v`` is SAT -> ``Verdict.CRIMINAL`` (``KB |= C_i``).
      3. ``-v`` is SAT and ``+v`` is UNSAT -> ``Verdict.INNOCENT`` (``KB |= ~C_i``).
      4. Both SAT -> ``Verdict.UNKNOWN``.

    Args:
        kb: Compiled CNF knowledge base from ``CNFEncoder.build_kb``.
        varmap: Primary variable mapping for the grid.
        cell: The target cell to classify.
        solver: DPLL solver instance (creates a default ``DPLLSolver()`` if None).

    Returns:
        A ``Classification`` with the resulting ``Verdict`` and recorded queries.
    """
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

    # Query 1: SAT(KB ^ ~C_i) -> test if cell can be INNOCENT (-var)
    res_neg = active_solver.solve(
        clauses=kb.clauses,
        num_vars=kb.num_vars,
        assumptions=(-var,),
    )
    q_neg = SatQueryRecord(
        cell=cell,
        assumption=-var,
        satisfiable=res_neg.satisfiable,
        stats=res_neg.stats,
    )

    # Query 2: SAT(KB ^ C_i) -> test if cell can be CRIMINAL (+var)
    res_pos = active_solver.solve(
        clauses=kb.clauses,
        num_vars=kb.num_vars,
        assumptions=(var,),
    )
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