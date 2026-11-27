"""Puzzle solution uniqueness checking using CNF blocking clauses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

from griductive.logic.dpll import DPLLSolver, SolverStats
from griductive.logic.encoder import CNFEncoder
from griductive.logic.varmap import VarMap
from griductive.model.cell import CellId, Status
from griductive.model.clue import Clue
from griductive.model.puzzle import PublicState


@dataclass(frozen=True)
class UniquenessReport:
    """Report detailing whether a puzzle or CNF formula has a unique model."""

    status: Literal["UNIQUE", "NOT_UNIQUE", "UNSAT"]
    models_found: int
    models: tuple[dict[int, bool] | Mapping[CellId, Status], ...]
    stats: SolverStats


def make_blocking_clause(
    model: Mapping[int, bool], n_primary: int
) -> tuple[int, ...]:
    """Construct a blocking clause over primary variables 1..n_primary.

    For each primary variable v:
      - If model[v] is True, the blocking literal is -v.
      - If model[v] is False, the blocking literal is +v.

    Returns:
        A tuple of integer literals representing the blocking clause.
    """
    if isinstance(n_primary, bool) or not isinstance(n_primary, int) or n_primary <= 0:
        raise ValueError("n_primary must be a positive integer")

    blocking_lits = []
    for var in range(1, n_primary + 1):
        val = model.get(var, False)
        blocking_lits.append(-var if val else var)

    return tuple(blocking_lits)


def check_uniqueness_cnf(
    clauses: Sequence[Sequence[int]],
    n_primary: int,
    num_vars: int,
    solver: DPLLSolver | None = None,
) -> UniquenessReport:
    """Check uniqueness of solution for integer CNF clauses.

    Finds up to 2 models using blocking clauses over primary variables.
    """
    if solver is None:
        solver = DPLLSolver()

    total_stats = SolverStats()

    # Step 1: Solve for initial model
    res1 = solver.solve(clauses, num_vars)
    total_stats.add(res1.stats)

    if not res1.satisfiable or res1.model is None:
        return UniquenessReport(
            status="UNSAT",
            models_found=0,
            models=(),
            stats=total_stats,
        )

    model1 = res1.model

    # Step 2: Add blocking clause over primary variables
    blocking_clause = make_blocking_clause(model1, n_primary)
    augmented_clauses = list(clauses) + [blocking_clause]

    # Step 3: Solve for second model
    res2 = solver.solve(augmented_clauses, num_vars)
    total_stats.add(res2.stats)

    if res2.satisfiable and res2.model is not None:
        model2 = res2.model
        return UniquenessReport(
            status="NOT_UNIQUE",
            models_found=2,
            models=(model1, model2),
            stats=total_stats,
        )

    return UniquenessReport(
        status="UNIQUE",
        models_found=1,
        models=(model1,),
        stats=total_stats,
    )


def check_uniqueness(
    state_or_clues: PublicState | Sequence[Clue],
    n: int | None = None,
    solver: DPLLSolver | None = None,
    encoder: CNFEncoder | None = None,
) -> UniquenessReport:
    """Check if a PublicState or set of clues forces a unique solution for an n x n grid."""
    if isinstance(state_or_clues, PublicState):
        state = state_or_clues
        if n is not None and n != state.n:
            raise ValueError(
                f"Provided n ({n}) does not match PublicState grid size ({state.n})"
            )
        grid_n = state.n
    elif isinstance(state_or_clues, (list, tuple)):
        if n is None or not isinstance(n, int) or n <= 0:
            raise ValueError("n must be a positive integer when passing a sequence of clues")
        grid_n = n
        unsolved = tuple(
            CellId(r, c) for r in range(grid_n) for c in range(grid_n)
        )
        state = PublicState(
            n=grid_n,
            revealed_clues=tuple(state_or_clues),
            proved={},
            unsolved=unsolved,
        )
    else:
        raise TypeError("state_or_clues must be a PublicState or Sequence[Clue]")

    if solver is None:
        solver = DPLLSolver()
    if encoder is None:
        encoder = CNFEncoder(grid_n)
    elif encoder.n != grid_n:
        raise ValueError(
            f"Encoder size ({encoder.n}) does not match grid size ({grid_n})"
        )

    # Build KB using build_kb from CNFEncoder
    kb = encoder.build_kb(state)

    report_cnf = check_uniqueness_cnf(kb.clauses, kb.n_primary, kb.num_vars, solver)

    # Convert models from variable ids to CellId -> Status mappings
    varmap = encoder.varmap
    converted_models = []
    for raw_model in report_cnf.models:
        cell_status_map: dict[CellId, Status] = {}
        for var in range(1, kb.n_primary + 1):
            cell = varmap.cell(var)
            is_criminal = raw_model.get(var, False)
            cell_status_map[cell] = Status.CRIMINAL if is_criminal else Status.INNOCENT
        converted_models.append(cell_status_map)

    return UniquenessReport(
        status=report_cnf.status,
        models_found=report_cnf.models_found,
        models=tuple(converted_models),
        stats=report_cnf.stats,
    )
