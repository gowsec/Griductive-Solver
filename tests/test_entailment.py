"""Unit tests for griductive.logic.entailment (ENT-01..ENT-08)."""

from __future__ import annotations

from itertools import product

from griductive.logic.dpll import DPLLSolver, SolverStats
from griductive.logic.encoder import CNFEncoder, KB
from griductive.logic.entailment import (
    Classification,
    SatQueryRecord,
    Verdict,
    classify,
)
from griductive.logic.varmap import VarMap
from griductive.model.cell import CellId, Status
from griductive.model.clue import Count, Different, Fact, Same
from griductive.model.puzzle import PublicState
from griductive.model.region import Region, RegionKind


def _make_state(
    n: int,
    revealed_clues: tuple = (),
    proved: dict[CellId, Status] | None = None,
) -> PublicState:
    """Create a deterministic PublicState for testing CNFEncoder.build_kb."""
    proved_dict = dict(proved) if proved is not None else {}
    unsolved = tuple(
        CellId(r, c)
        for r in range(n)
        for c in range(n)
        if CellId(r, c) not in proved_dict
    )
    return PublicState(
        n=n,
        revealed_clues=tuple(revealed_clues),
        proved=proved_dict,
        unsolved=unsolved,
    )


def _brute_force_verdict(kb: KB, var: int) -> Verdict:
    """Gold-standard brute-force entailment check over all 2^num_vars assignments."""
    has_true_model = False
    has_false_model = False

    for bits in product((False, True), repeat=kb.num_vars):
        model = {i + 1: bits[i] for i in range(kb.num_vars)}
        if all(
            any((model[abs(lit)] if lit > 0 else not model[abs(lit)]) for lit in clause)
            for clause in kb.clauses
        ):
            if model[var]:
                has_true_model = True
            else:
                has_false_model = True

    if not has_true_model and not has_false_model:
        return Verdict.INCONSISTENT
    if has_true_model and not has_false_model:
        return Verdict.CRIMINAL
    if not has_true_model and has_false_model:
        return Verdict.INNOCENT
    return Verdict.UNKNOWN


def test_ent_01_example_kb_classify_b_is_criminal() -> None:
    """ENT-01: KB ví dụ trong đề (A ∨ B) ∧ (¬A ∨ B), classify(B) -> CRIMINAL; 2 truy vấn ghi lại."""
    varmap = VarMap(2)
    cell_b = CellId(0, 1)  # var = 2
    kb = KB(clauses=[(1, 2), (-1, 2)], n_primary=4, n_aux=0)
    solver = DPLLSolver()

    res = classify(kb, varmap, cell_b, solver)

    assert isinstance(res, Classification)
    assert res.verdict is Verdict.CRIMINAL
    assert len(res.queries) == 2


def test_ent_02_example_kb_classify_a_is_unknown() -> None:
    """ENT-02: KB ví dụ trong đề (A ∨ B) ∧ (¬A ∨ B), classify(A) -> UNKNOWN."""
    varmap = VarMap(2)
    cell_a = CellId(0, 0)  # var = 1
    kb = KB(clauses=[(1, 2), (-1, 2)], n_primary=4, n_aux=0)
    solver = DPLLSolver()

    res = classify(kb, varmap, cell_a, solver)

    assert res.verdict is Verdict.UNKNOWN
    assert len(res.queries) == 2


def test_ent_03_inconsistent_kb_returns_inconsistent_for_all_cells() -> None:
    """ENT-03: KB UNSAT ((A) ∧ (¬A)) -> INCONSISTENT cho mọi ô."""
    n = 2
    encoder = CNFEncoder(n)
    solver = DPLLSolver()
    cell_a = CellId(0, 0)

    state = _make_state(
        n,
        revealed_clues=(
            Fact(id="clue@A1", cell=cell_a, status=Status.CRIMINAL),
            Fact(id="clue@B1", cell=cell_a, status=Status.INNOCENT),
        ),
    )
    kb = encoder.build_kb(state)

    for r in range(n):
        for c in range(n):
            res = classify(kb, encoder.varmap, CellId(r, c), solver)
            assert res.verdict is Verdict.INCONSISTENT


def test_ent_04_classify_innocent() -> None:
    """ENT-04: INNOCENT: KB = (¬A ∨ ¬B) ∧ (A) => classify(B) -> INNOCENT."""
    n = 2
    encoder = CNFEncoder(n)
    solver = DPLLSolver()
    cell_a = CellId(0, 0)
    cell_b = CellId(0, 1)

    region_ab = Region(kind=RegionKind.CELLS, cells=(cell_a, cell_b))
    state = _make_state(
        n,
        revealed_clues=(
            Count(id="clue@A1", op=Count.LE, k=1, region=region_ab),
            Fact(id="clue@B1", cell=cell_a, status=Status.CRIMINAL),
        ),
    )
    kb = encoder.build_kb(state)
    res = classify(kb, encoder.varmap, cell_b, solver)

    assert res.verdict is Verdict.INNOCENT


def test_ent_05_classification_queries_fields() -> None:
    """ENT-05: Classification.queries: Mỗi bản ghi có assumption, satisfiable, stats."""
    n = 2
    encoder = CNFEncoder(n)
    solver = DPLLSolver()
    cell_a = CellId(0, 0)
    cell_b = CellId(0, 1)

    state = _make_state(
        n,
        revealed_clues=(Same(id="clue@A1", a=cell_a, b=cell_b),),
        proved={cell_a: Status.CRIMINAL},
    )
    kb = encoder.build_kb(state)
    res = classify(kb, encoder.varmap, cell_b, solver)

    assert res.verdict is Verdict.CRIMINAL
    assert len(res.queries) == 2
    for q in res.queries:
        assert isinstance(q, SatQueryRecord)
        assert q.cell == cell_b
        assert q.assumption in (-2, 2)
        assert isinstance(q.satisfiable, bool)
        assert isinstance(q.stats, SolverStats)


def test_ent_06_monotonicity_invariant_with_build_kb() -> None:
    """ENT-06: Bất biến đơn điệu: thêm clue hợp lệ vào KB, ô đã CRIMINAL/INNOCENT không đổi."""
    n = 3
    encoder = CNFEncoder(n)
    solver = DPLLSolver()
    a1, b1, c1 = CellId(0, 0), CellId(0, 1), CellId(0, 2)

    clues_1 = (
        Fact(id="clue@A1", cell=a1, status=Status.CRIMINAL),
        Same(id="clue@B1", a=a1, b=b1),
    )
    kb_1 = encoder.build_kb(_make_state(n, revealed_clues=clues_1))
    assert classify(kb_1, encoder.varmap, a1, solver).verdict is Verdict.CRIMINAL
    assert classify(kb_1, encoder.varmap, b1, solver).verdict is Verdict.CRIMINAL
    assert classify(kb_1, encoder.varmap, c1, solver).verdict is Verdict.UNKNOWN

    clues_2 = clues_1 + (Different(id="clue@C1", a=b1, b=c1),)
    kb_2 = encoder.build_kb(_make_state(n, revealed_clues=clues_2))
    assert classify(kb_2, encoder.varmap, a1, solver).verdict is Verdict.CRIMINAL
    assert classify(kb_2, encoder.varmap, b1, solver).verdict is Verdict.CRIMINAL
    assert classify(kb_2, encoder.varmap, c1, solver).verdict is Verdict.INNOCENT


def test_ent_07_matches_brute_force_on_20_small_kbs() -> None:
    """ENT-07: Đối chiếu với vét cạn trên 20 KB nhỏ -> classify khớp 'đúng trong mọi mô hình'."""
    varmap = VarMap(2)
    solver = DPLLSolver()

    clause_sets: list[list[tuple[int, ...]]] = [
        [],
        [(1,)],
        [(-2,)],
        [(1, 2), (-1, 2)],
        [(-1, -2), (1,)],
        [(1, 2), (-1, -2)],
        [(1, -2), (-1, 2), (2, -3), (-2, 3), (3,)],
        [(1, 2, 3), (-1,), (-2,)],
        [(-1, -2, -3), (1,), (2,)],
        [(1, 2), (2, 3), (3, 4), (-1, -4)],
        [(1,), (-1,)],
        [(1, 2), (1, -2), (-1, 2), (-1, -2)],
        [(1, -2), (2, -3), (3, -4), (4,)],
        [(1, -2), (2, -3), (3, -4), (-1,)],
        [(1, 2), (-1, 3), (-2, 3), (-3, 4)],
        [(-1, -2), (-2, -3), (2,)],
        [(1, 4), (-1, 4), (-4, -3)],
        [(1, 2, 3, 4), (-1,), (-2,), (-3,)],
        [(-1, 2), (-2, 1), (-3, -4)],
        [(2, 3), (-2, 3), (3, 4), (-3, -4)],
    ]
    assert len(clause_sets) == 20

    cells = [CellId(r, c) for r in range(2) for c in range(2)]
    for clauses in clause_sets:
        kb = KB(clauses=clauses, n_primary=4, n_aux=0)
        for cell in cells:
            expected = _brute_force_verdict(kb, varmap.var(cell))
            actual = classify(kb, varmap, cell, solver).verdict
            assert actual is expected


def test_ent_08_only_forced_cells_are_classified() -> None:
    """ENT-08: Một ô cố định trong mọi mô hình thỏa mà ô khác tự do -> chỉ ô bị buộc được phân loại."""
    n = 2
    encoder = CNFEncoder(n)
    solver = DPLLSolver()
    a1, b1, a2, b2 = CellId(0, 0), CellId(0, 1), CellId(1, 0), CellId(1, 1)

    row0 = Region(kind=RegionKind.ROW, row=0)
    row1 = Region(kind=RegionKind.ROW, row=1)
    state = _make_state(
        n,
        revealed_clues=(
            Count(id="clue@A1", op=Count.EQ, k=2, region=row0),
            Count(id="clue@A2", op=Count.EQ, k=1, region=row1),
        ),
    )
    kb = encoder.build_kb(state)

    assert classify(kb, encoder.varmap, a1, solver).verdict is Verdict.CRIMINAL
    assert classify(kb, encoder.varmap, b1, solver).verdict is Verdict.CRIMINAL
    assert classify(kb, encoder.varmap, a2, solver).verdict is Verdict.UNKNOWN
    assert classify(kb, encoder.varmap, b2, solver).verdict is Verdict.UNKNOWN