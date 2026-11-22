"""LogicAgent implementation providing deduction oracle, forced-move search, and hints."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import time

from griductive.logic.dpll import DPLLSolver, SolverStats, SolverTimeout
from griductive.logic.encoder import CNFEncoder, KB
from griductive.logic.entailment import (
    Classification,
    SatQueryRecord,
    Verdict,
    classify as entailment_classify,
)
from griductive.logic.varmap import VarMap
from griductive.model.cell import CellId
from griductive.model.puzzle import PublicState


@dataclass(frozen=True)
class Hint:
    """A deduction hint pointing to a provable cell and its relevant revealed clues."""

    cell: CellId
    verdict: Verdict
    related_clue_ids: tuple[str, ...]
    queries: tuple[SatQueryRecord, ...]


class LogicAgent:
    """Purely deductive agent operating strictly on ``PublicState`` (Principle P1)."""

    def __init__(
        self,
        encoder_factory: Callable[[int], CNFEncoder] = CNFEncoder,
        solver_factory: Callable[[], DPLLSolver] = DPLLSolver,
        timeout: float | None = None,
    ) -> None:
        """Initialize the logic agent with configurable encoder, solver, and timeout."""
        self._encoder_factory = encoder_factory
        self._solver_factory = solver_factory
        self._timeout = timeout
        self._last_queries: tuple[SatQueryRecord, ...] = ()
        self._last_verdict: Verdict | None = None

    @property
    def last_queries(self) -> tuple[SatQueryRecord, ...]:
        """Return the SAT queries recorded during the most recent deduction call."""
        return self._last_queries

    @property
    def last_verdict(self) -> Verdict | None:
        """Return the terminal/cell verdict observed in the most recent deduction call."""
        return self._last_verdict

    def _resolve_timeout(self, timeout: float | None) -> float | None:
        return self._timeout if timeout is None else timeout

    @staticmethod
    def _attach_accumulated_stats(
        exc: SolverTimeout, accumulated_queries: list[SatQueryRecord]
    ) -> None:
        combined = SolverStats()
        for q in accumulated_queries:
            combined.add(q.stats)
        if exc.stats is not None:
            combined.add(exc.stats)
        exc.stats = combined

    def _compile_state(self, state: PublicState) -> tuple[KB, VarMap, DPLLSolver]:
        """Build the CNF knowledge base and variable map from ``PublicState``."""
        if not isinstance(state, PublicState):
            raise TypeError("state must be a PublicState instance")
        encoder = self._encoder_factory(state.n)
        kb = encoder.build_kb(state)
        solver = self._solver_factory()
        return kb, encoder.varmap, solver

    def classify(
        self,
        state: PublicState,
        cell: CellId,
        timeout: float | None = None,
    ) -> Classification:
        """Classify a single cell given the current ``PublicState``."""
        kb, varmap, solver = self._compile_state(state)
        effective_timeout = self._resolve_timeout(timeout)
        result = entailment_classify(kb, varmap, cell, solver, timeout=effective_timeout)
        self._last_queries = result.queries
        self._last_verdict = result.verdict
        return result

    def classify_all(
        self,
        state: PublicState,
        timeout: float | None = None,
    ) -> dict[CellId, Classification]:
        """Classify all currently unsolved cells in deterministic row-major order."""
        kb, varmap, solver = self._compile_state(state)
        effective_timeout = self._resolve_timeout(timeout)
        deadline = (
            time.perf_counter() + effective_timeout
            if effective_timeout is not None
            else None
        )

        results: dict[CellId, Classification] = {}
        accumulated_queries: list[SatQueryRecord] = []

        for cell in sorted(state.unsolved):
            remaining = (deadline - time.perf_counter()) if deadline is not None else None
            try:
                classification = entailment_classify(
                    kb, varmap, cell, solver, timeout=remaining
                )
            except SolverTimeout as exc:
                self._last_queries = tuple(accumulated_queries)
                self._attach_accumulated_stats(exc, accumulated_queries)
                raise

            results[cell] = classification
            accumulated_queries.extend(classification.queries)

        self._last_queries = tuple(accumulated_queries)
        if any(c.verdict is Verdict.INCONSISTENT for c in results.values()):
            self._last_verdict = Verdict.INCONSISTENT
        elif any(
            c.verdict in (Verdict.CRIMINAL, Verdict.INNOCENT) for c in results.values()
        ):
            self._last_verdict = next(
                c.verdict
                for c in results.values()
                if c.verdict in (Verdict.CRIMINAL, Verdict.INNOCENT)
            )
        else:
            self._last_verdict = Verdict.UNKNOWN

        return results

    def next_forced(
        self,
        state: PublicState,
        timeout: float | None = None,
    ) -> tuple[CellId, Verdict] | None:
        """Find the first unsolved cell (in row-major order) with a forced verdict."""
        kb, varmap, solver = self._compile_state(state)
        effective_timeout = self._resolve_timeout(timeout)
        deadline = (
            time.perf_counter() + effective_timeout
            if effective_timeout is not None
            else None
        )
        accumulated_queries: list[SatQueryRecord] = []

        for cell in sorted(state.unsolved):
            remaining = (deadline - time.perf_counter()) if deadline is not None else None
            try:
                classification = entailment_classify(
                    kb, varmap, cell, solver, timeout=remaining
                )
            except SolverTimeout as exc:
                self._last_queries = tuple(accumulated_queries)
                self._attach_accumulated_stats(exc, accumulated_queries)
                raise

            accumulated_queries.extend(classification.queries)

            if classification.verdict is Verdict.INCONSISTENT:
                self._last_queries = tuple(accumulated_queries)
                self._last_verdict = Verdict.INCONSISTENT
                return None

            if classification.verdict in (Verdict.CRIMINAL, Verdict.INNOCENT):
                self._last_queries = tuple(accumulated_queries)
                self._last_verdict = classification.verdict
                return cell, classification.verdict

        self._last_queries = tuple(accumulated_queries)
        self._last_verdict = Verdict.UNKNOWN
        return None

    def hint(
        self,
        state: PublicState,
        timeout: float | None = None,
    ) -> Hint | None:
        """Produce a hint for the first row-major forced cell without reading any solution."""
        kb, varmap, solver = self._compile_state(state)
        effective_timeout = self._resolve_timeout(timeout)
        deadline = (
            time.perf_counter() + effective_timeout
            if effective_timeout is not None
            else None
        )
        accumulated_queries: list[SatQueryRecord] = []

        for cell in sorted(state.unsolved):
            remaining = (deadline - time.perf_counter()) if deadline is not None else None
            try:
                classification = entailment_classify(
                    kb, varmap, cell, solver, timeout=remaining
                )
            except SolverTimeout as exc:
                self._last_queries = tuple(accumulated_queries)
                self._attach_accumulated_stats(exc, accumulated_queries)
                raise

            accumulated_queries.extend(classification.queries)

            if classification.verdict is Verdict.INCONSISTENT:
                self._last_queries = tuple(accumulated_queries)
                self._last_verdict = Verdict.INCONSISTENT
                return None

            if classification.verdict in (Verdict.CRIMINAL, Verdict.INNOCENT):
                related_ids = tuple(
                    clue.id
                    for clue in state.revealed_clues
                    if cell in clue.cells(state.n)
                )
                self._last_queries = tuple(accumulated_queries)
                self._last_verdict = classification.verdict
                return Hint(
                    cell=cell,
                    verdict=classification.verdict,
                    related_clue_ids=related_ids,
                    queries=classification.queries,
                )

        self._last_queries = tuple(accumulated_queries)
        self._last_verdict = Verdict.UNKNOWN
        return None