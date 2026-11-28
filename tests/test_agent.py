"""Unit tests for griductive.logic.agent (AGT-01..AGT-09) and architecture isolation."""

from __future__ import annotations

import ast
import json
from itertools import product
from pathlib import Path
from typing import Callable

import pytest

from griductive.logic.agent import Hint, LogicAgent
from griductive.logic.encoder import CNFEncoder
from griductive.logic.entailment import Classification, Verdict
from griductive.model.cell import CellId, Character, Status
from griductive.model.clue import Clue, Count, Different, Fact, Same
from griductive.model.puzzle import PublicState, Puzzle
from griductive.model.region import Region, RegionKind
from griductive.logic.dpll import SolverTimeout
from griductive.io.loader import PuzzleError, load_puzzle

def _make_state(
    n: int,
    clues: tuple[Clue, ...] = (),
    proved: dict[CellId, Status] | None = None,
) -> PublicState:
    """Helper to construct a valid PublicState with row-major unsolved cells."""
    proved_map = dict(proved) if proved is not None else {}
    unsolved = tuple(
        CellId(r, c)
        for r in range(n)
        for c in range(n)
        if CellId(r, c) not in proved_map
    )
    return PublicState(
        n=n,
        revealed_clues=clues,
        proved=proved_map,
        unsolved=unsolved,
    )


def _all_valid_primary_models(state: PublicState) -> list[dict[CellId, Status]]:
    """Brute-force all primary variable assignments satisfying a PublicState's KB."""
    encoder = CNFEncoder(state.n)
    kb = encoder.build_kb(state)
    varmap = encoder.varmap
    valid_models: list[dict[CellId, Status]] = []

    for bits in product((False, True), repeat=kb.num_vars):
        assignment = {i + 1: bits[i] for i in range(kb.num_vars)}
        if all(
            any(assignment[abs(lit)] if lit > 0 else not assignment[abs(lit)] for lit in clause)
            for clause in kb.clauses
        ):
            cell_map = {
                varmap.cell(v): (Status.CRIMINAL if assignment[v] else Status.INNOCENT)
                for v in range(1, kb.n_primary + 1)
            }
            valid_models.append(cell_map)

    return valid_models


def test_agt_01_classify_all_returns_all_unsolved_cells() -> None:
    """AGT-01: classify_all trả đủ mọi ô chưa giải, không bỏ sót."""
    n = 3
    a1, b1, c2 = CellId(0, 0), CellId(0, 1), CellId(1, 2)
    state = _make_state(
        n,
        clues=(Same(id="clue@A1", a=a1, b=b1),),
        proved={a1: Status.CRIMINAL, c2: Status.INNOCENT},
    )
    agent = LogicAgent()
    results = agent.classify_all(state)

    assert set(results.keys()) == set(state.unsolved)
    assert len(results) == n * n - 2
    assert list(results.keys()) == sorted(state.unsolved)
    assert results[b1].verdict is Verdict.CRIMINAL


def test_agt_02_next_forced_picks_first_in_row_major_order() -> None:
    """AGT-02: next_forced chọn row-major khi có nhiều ô forced cùng lúc."""
    n = 3
    a1 = CellId(0, 0)
    c1 = CellId(0, 2)
    b2 = CellId(1, 1)
    c3 = CellId(2, 2)

    # A1 đã mở. Cả C1 (hàng 0, cột 2), B2 (hàng 1, cột 1) và C3 (hàng 2, cột 2) đều bị forced.
    # Theo thứ tự row-major, C1 (0, 2) đứng trước B2 (1, 1) và C3 (2, 2).
    state = _make_state(
        n,
        clues=(
            Fact(id="clue@C3", cell=c3, status=Status.CRIMINAL),
            Fact(id="clue@B2", cell=b2, status=Status.INNOCENT),
            Same(id="clue@A1", a=a1, b=c1),
        ),
        proved={a1: Status.CRIMINAL},
    )
    agent = LogicAgent()
    forced = agent.next_forced(state)

    assert forced is not None
    cell, verdict = forced
    assert cell == c1
    assert verdict is Verdict.CRIMINAL


def test_agt_03_next_forced_returns_none_when_no_cell_forced() -> None:
    """AGT-03: next_forced khi không có ô forced trả về None."""
    n = 2
    a1, b1 = CellId(0, 0), CellId(0, 1)
    # Chỉ biết A1 và B1 khác nhau, chưa mở ô nào -> không ô nào bị buộc
    state = _make_state(
        n,
        clues=(Different(id="clue@A1", a=a1, b=b1),),
    )
    agent = LogicAgent()

    assert agent.next_forced(state) is None


def test_agt_04_agent_never_guesses_across_10_states() -> None:
    """AGT-04: Không đoán: trên 10 trạng thái, mọi verdict mà next_forced đưa ra đúng trong mọi mô hình."""
    n = 2
    a1, b1, a2, b2 = CellId(0, 0), CellId(0, 1), CellId(1, 0), CellId(1, 1)
    row0 = Region(kind=RegionKind.ROW, row=0)
    row1 = Region(kind=RegionKind.ROW, row=1)
    col0 = Region(kind=RegionKind.COL, col=0)

    states = [
        _make_state(n),  # 1. Trống -> None
        _make_state(n, clues=(Same("c1", a1, b1),)),  # 2. Chưa đủ thông tin -> None
        _make_state(n, clues=(Same("c1", a1, b1),), proved={a1: Status.CRIMINAL}),  # 3. Buộc B1=CRIMINAL
        _make_state(n, clues=(Different("c1", a1, a2),), proved={a1: Status.CRIMINAL}),  # 4. Buộc A2=INNOCENT
        _make_state(n, clues=(Count("c1", Count.EQ, 2, row0),)),  # 5. Buộc A1=CRIMINAL
        _make_state(n, clues=(Count("c1", Count.EQ, 0, col0),)),  # 6. Buộc A1=INNOCENT
        _make_state(n, clues=(Count("c1", Count.EQ, 1, row0),), proved={a1: Status.CRIMINAL}),  # 7. Buộc B1=INNOCENT
        _make_state(n, clues=(Count("c1", Count.EQ, 1, row1),)),  # 8. Không đủ thông tin -> None
        _make_state(n, clues=(Count("c1", Count.LE, 1, row1), Fact("c2", a2, Status.CRIMINAL))),  # 9. Buộc A2/B2
        _make_state(n, clues=(Same("c1", a1, b2), Different("c2", b2, a2)), proved={a1: Status.INNOCENT}),  # 10. Buộc A2/B2
    ]
    assert len(states) == 10

    agent = LogicAgent()
    for state in states:
        models = _all_valid_primary_models(state)
        assert len(models) > 0, "Test state must be satisfiable"

        forced = agent.next_forced(state)
        if forced is not None:
            cell, verdict = forced
            expected_status = Status.CRIMINAL if verdict is Verdict.CRIMINAL else Status.INNOCENT
            # Chứng minh ô được chọn mang cùng trạng thái trong MỌI mô hình thỏa KB
            assert all(m[cell] is expected_status for m in models)
        else:
            # Nếu trả về None, kiểm tra thực sự không có ô chưa giải nào cố định trong mọi mô hình
            for cell in state.unsolved:
                statuses_in_models = {m[cell] for m in models}
                assert len(statuses_in_models) > 1


def test_agt_05_hint_returns_forced_cell_and_related_revealed_clues() -> None:
    """AGT-05: hint trả ô forced + clue đã lộ có chứa ô đó trong cells()."""
    n = 3
    a1, b1, c3 = CellId(0, 0), CellId(0, 1), CellId(2, 2)
    row0 = Region(kind=RegionKind.ROW, row=0)

    clue_same = Same(id="clue@A1", a=a1, b=b1)
    clue_row0 = Count(id="clue@B1", op=Count.GE, k=1, region=row0)
    clue_unrel = Fact(id="clue@C3", cell=c3, status=Status.INNOCENT)

    state = _make_state(
        n,
        clues=(clue_same, clue_row0, clue_unrel),
        proved={a1: Status.CRIMINAL},
    )
    agent = LogicAgent()
    hint = agent.hint(state)

    assert isinstance(hint, Hint)
    assert hint.cell == b1
    assert hint.verdict is Verdict.CRIMINAL
    revealed_ids = {c.id for c in state.revealed_clues}
    assert set(hint.related_clue_ids).issubset(revealed_ids)
    # B1 nằm trong clue@A1 (Same A1, B1) và clue@B1 (ROW 0), không nằm trong clue@C3
    assert hint.related_clue_ids == ("clue@A1", "clue@B1")
    assert len(hint.queries) == 2


def test_agt_06_hint_when_stuck_returns_none() -> None:
    """AGT-06: hint khi kẹt báo không có hint (trả về None, không bịa)."""
    n = 2
    a1, b1 = CellId(0, 0), CellId(0, 1)
    state = _make_state(
        n,
        clues=(Different(id="clue@A1", a=a1, b=b1),),
    )
    agent = LogicAgent()

    assert agent.hint(state) is None


def test_agt_07_agent_and_hint_do_not_depend_on_puzzle_solution() -> None:
    """AGT-07: Hint/agent không phụ thuộc solution: đảo Puzzle.solution kết quả vẫn giống hệt."""
    n = 2
    cells = [CellId(r, c) for r in range(n) for c in range(n)]
    a1, b1, a2, b2 = cells

    clues_map = {
        a1: Same(id="clue@A1", a=a1, b=b1),
        b1: Different(id="clue@B1", a=b1, b=a2),
        a2: Same(id="clue@A2", a=a2, b=b2),
        b2: Fact(id="clue@B2", cell=b2, status=Status.INNOCENT),
    }
    chars = {c: Character(cell=c, name=f"Char_{c}", job="Tester") for c in cells}

    # Puzzle 1 với solution chuẩn
    puzzle_1 = Puzzle(
        n=n,
        characters=chars,
        solution={
            a1: Status.CRIMINAL,
            b1: Status.CRIMINAL,
            a2: Status.INNOCENT,
            b2: Status.INNOCENT,
        },
        clues=clues_map,
        initial_revealed=frozenset({a1}),
    )
    # Puzzle 2 với solution bị đảo ngược hoàn toàn
    puzzle_2 = Puzzle(
        n=n,
        characters=chars,
        solution={
            a1: Status.INNOCENT,
            b1: Status.INNOCENT,
            a2: Status.CRIMINAL,
            b2: Status.CRIMINAL,
        },
        clues=clues_map,
        initial_revealed=frozenset({a1}),
    )

    # PublicState sinh ra từ trạng thái công khai (không chứa solution)
    state_1 = _make_state(n, clues=(puzzle_1.clues[a1],), proved={a1: Status.CRIMINAL})
    state_2 = _make_state(n, clues=(puzzle_2.clues[a1],), proved={a1: Status.CRIMINAL})

    agent = LogicAgent()
    assert agent.next_forced(state_1) == agent.next_forced(state_2)

    hint_1 = agent.hint(state_1)
    hint_2 = agent.hint(state_2)
    assert hint_1 is not None and hint_2 is not None
    assert hint_1.cell == hint_2.cell == b1
    assert hint_1.verdict == hint_2.verdict == Verdict.CRIMINAL
    assert hint_1.related_clue_ids == hint_2.related_clue_ids


def test_agt_08_agent_on_inconsistent_state() -> None:
    """AGT-08: Agent trên trạng thái mâu thuẫn phát hiện INCONSISTENT, không trả verdict forced."""
    n = 2
    a1, b1 = CellId(0, 0), CellId(0, 1)
    state = _make_state(
        n,
        clues=(
            Fact(id="clue@A1", cell=a1, status=Status.CRIMINAL),
            Fact(id="clue@B1", cell=a1, status=Status.INNOCENT),
        ),
    )
    agent = LogicAgent()

    cls_res = agent.classify(state, b1)
    assert cls_res.verdict is Verdict.INCONSISTENT
    assert agent.next_forced(state) is None
    assert agent.last_verdict is Verdict.INCONSISTENT
    assert agent.hint(state) is None


def test_bad_contradiction_fixture_reaches_agent_inconsistent_path() -> None:
    """The fixture is rejected by the loader, but its contradictory public clues make an inconsistent KB."""
    puzzle_path = Path(__file__).resolve().parents[1] / "puzzles" / "bad_contradiction.json"
    with puzzle_path.open(encoding="utf-8") as puzzle_file:
        raw_puzzle = json.load(puzzle_file)

    # The loader correctly rejects this fixture because B1's clue conflicts with
    # the supplied hidden solution. That is separate from agent behavior.
    with pytest.raises(PuzzleError, match="clue is not satisfied"):
        load_puzzle(puzzle_path)

    raw_facts = (raw_puzzle["clues"]["A1"], raw_puzzle["clues"]["B1"])
    facts = tuple(
        Fact(
            id=f"clue@{cell}",
            cell=CellId.parse(raw_fact["cell"]),
            status=Status(raw_fact["status"]),
        )
        for cell, raw_fact in zip(("A1", "B1"), raw_facts, strict=True)
    )
    a1 = CellId.parse("A1")
    state = _make_state(2, clues=facts, proved={})

    result = LogicAgent().classify(state, a1)
    assert result.verdict is Verdict.INCONSISTENT


def test_agt_09_classify_matches_engine_oracle_signature() -> None:
    """AGT-09: classify dùng làm oracle cho engine, khớp Oracle signature."""
    n = 2
    a1, b1 = CellId(0, 0), CellId(0, 1)
    state = _make_state(
        n,
        clues=(Same(id="clue@A1", a=a1, b=b1),),
        proved={a1: Status.CRIMINAL},
    )
    agent = LogicAgent()

    # Gán vào biến kiểu Oracle = Callable[[PublicState, CellId], Classification]
    oracle: Callable[[PublicState, CellId], Classification] = agent.classify
    result = oracle(state, b1)

    assert isinstance(result, Classification)
    assert result.verdict is Verdict.CRIMINAL
    assert len(result.queries) == 2


def test_agent_isolation_no_engine_or_solution_access() -> None:
    """ISO-01 & ISO-03: Quét AST toàn bộ griductive/logic/ đảm bảo không import engine/gui/orchestration và không đọc .solution."""
    logic_dir = Path(__file__).resolve().parents[1] / "griductive" / "logic"
    forbidden_prefixes = (
        "griductive.engine",
        "griductive.orchestration",
        "griductive.gui",
        "engine",
        "orchestration",
        "gui",
    )

    py_files = list(logic_dir.glob("*.py"))
    assert len(py_files) > 0

    for py_file in py_files:
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden_prefixes), (
                        f"Forbidden import '{alias.name}' in {py_file.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                assert not module_name.startswith(forbidden_prefixes), (
                    f"Forbidden from-import '{module_name}' in {py_file.name}"
                )
            elif isinstance(node, ast.Attribute):
                assert node.attr != "solution", (
                    f"Forbidden '.solution' attribute access in {py_file.name}"
                )

def test_agent_timeout_propagates_with_stats() -> None:
    n = 2
    a1, b1 = CellId(0, 0), CellId(0, 1)
    state = _make_state(n, clues=(Same("clue@A1", a1, b1),))
    agent = LogicAgent(timeout=-1.0)

    with pytest.raises(SolverTimeout) as exc_info:
        agent.next_forced(state)
    assert exc_info.value.stats is not None


def test_hint_and_next_forced_record_consistent_last_queries() -> None:
    n = 2
    a1, b1, a2 = CellId(0, 0), CellId(0, 1), CellId(1, 0)
    # A1 chưa forced (UNKNOWN), B1 bị forced (CRIMINAL) -> cả hint và next_forced đều quét A1 rồi B1
    state = _make_state(n, clues=(Fact("clue@B1", b1, Status.CRIMINAL),))
    agent = LogicAgent()

    agent.next_forced(state)
    nf_queries = agent.last_queries

    agent.hint(state)
    hint_queries = agent.last_queries

    assert len(nf_queries) == len(hint_queries) == 4
    assert [(q.cell, q.assumption) for q in nf_queries] == [
        (q.cell, q.assumption) for q in hint_queries
    ]
