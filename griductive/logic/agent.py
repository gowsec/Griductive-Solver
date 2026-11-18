"""LogicAgent implementation providing deduction oracle, forced-move search, and hints."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from griductive.logic.dpll import DPLLSolver
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
    ) -> None:
        """Initialize the logic agent with configurable encoder and solver factories."""
        self._encoder_factory = encoder_factory
        self._solver_factory = solver_factory
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

    def _compile_state(self, state: PublicState) -> tuple[KB, VarMap, DPLLSolver]:
        """Build the CNF knowledge base and variable map from ``PublicState``."""
        if not isinstance(state, PublicState):
            raise TypeError("state must be a PublicState instance")
        encoder = self._encoder_factory(state.n)
        kb = encoder.build_kb(state)
        solver = self._solver_factory()
        return kb, encoder.varmap, solver

    def classify(self, state: PublicState, cell: CellId) -> Classification:
        """Classify a single cell given the current ``PublicState``.

        Matches the ``Oracle = Callable[[PublicState, CellId], Classification]``
        contract required by ``GameEngine``.
        """
        kb, varmap, solver = self._compile_state(state)
        result = entailment_classify(kb, varmap, cell, solver)
        self._last_queries = result.queries
        self._last_verdict = result.verdict
        return result

    def classify_all(self, state: PublicState) -> dict[CellId, Classification]:
        """Classify all currently unsolved cells in deterministic row-major order."""
        kb, varmap, solver = self._compile_state(state)
        results: dict[CellId, Classification] = {}
        accumulated_queries: list[SatQueryRecord] = []

        # Sort unsolved cells to guarantee deterministic row-major iteration (Principle P8)
        for cell in sorted(state.unsolved):
            classification = entailment_classify(kb, varmap, cell, solver)
            results[cell] = classification
            accumulated_queries.extend(classification.queries)

        self._last_queries = tuple(accumulated_queries)
        if any(c.verdict is Verdict.INCONSISTENT for c in results.values()):
            self._last_verdict = Verdict.INCONSISTENT
        elif any(c.verdict in (Verdict.CRIMINAL, Verdict.INNOCENT) for c in results.values()):
            self._last_verdict = next(
                c.verdict
                for c in results.values()
                if c.verdict in (Verdict.CRIMINAL, Verdict.INNOCENT)
            )
        else:
            self._last_verdict = Verdict.UNKNOWN

        return results

    def next_forced(self, state: PublicState) -> tuple[CellId, Verdict] | None:
        """Find the first unsolved cell (in row-major order) with a forced verdict.

        Returns:
            ``(cell, verdict)`` where ``verdict`` is ``CRIMINAL`` or ``INNOCENT``,
            or ``None`` if no unsolved cell is logically forced (or if KB is inconsistent).
        """
        kb, varmap, solver = self._compile_state(state)
        accumulated_queries: list[SatQueryRecord] = []

        for cell in sorted(state.unsolved):
            classification = entailment_classify(kb, varmap, cell, solver)
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

    def hint(self, state: PublicState) -> Hint | None:
        """Produce a hint for the first row-major forced cell without reading any solution.

        Identifies the first forced unsolved cell and collects the IDs of all
        revealed clues whose ``cells(n)`` include that cell. If no cell is forced
        (stuck or inconsistent), returns ``None``.
        """
        kb, varmap, solver = self._compile_state(state)
        accumulated_queries: list[SatQueryRecord] = []

        for cell in sorted(state.unsolved):
            classification = entailment_classify(kb, varmap, cell, solver)
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
                self._last_queries = classification.queries
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