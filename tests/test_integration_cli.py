"""Test cho CLI tích hợp M1-04 (``griductive.orchestration.integration_cli``).

Nhóm test ``E2E-*`` (xem docs/TEST_CASES.md). Các test độc lập (không cần code của
M2/M3/M4) luôn chạy; test cần module thật dùng ``pytest.importorskip`` nên tự bỏ
qua khi module chưa được merge.
"""

from __future__ import annotations

import pathlib
from collections import namedtuple
from types import SimpleNamespace

import pytest

from griductive.orchestration import integration_cli as cli

DATA = pathlib.Path(__file__).parent / "data" / "3x3_demo.json"
Cell = namedtuple("Cell", "row col")


# --------------------------------------------------------------------------- #
# Phân tích CNF viết tay
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text, expected",
    [
        ("1 2 0; -1 2 0", [(1, 2), (-1, 2)]),
        ("1 2; -1 2", [(1, 2), (-1, 2)]),  # không có số 0 cuối clause
        ("  1 2 0 ;; -1 2 0 ; ", [(1, 2), (-1, 2)]),  # khoảng trắng, đoạn rỗng
        ("c ghi chú\np cnf 2 2\n1 2 0\n-1 2 0\n", [(1, 2), (-1, 2)]),  # DIMACS
        ("1 2\n-3 0\n4 0", [(1, 2, -3), (4,)]),  # clause trải nhiều dòng
        ("0", [()]),  # clause rỗng
        ("", []),
    ],
)
def test_e2e_parse_clauses(text, expected):
    """E2E-10: phân tích CNF thô."""
    assert cli.parse_clauses(text) == expected


def test_e2e_parse_clauses_rejects_garbage():
    """E2E-11: token không phải số nguyên bị từ chối rõ ràng."""
    with pytest.raises(ValueError):
        cli.parse_clauses("1 x 0")


# --------------------------------------------------------------------------- #
# Bộ giải vét cạn và selftest
# --------------------------------------------------------------------------- #
def test_e2e_bruteforce_spec_example():
    """E2E-12: ví dụ trong đề (mục 3.4): KB ⊨ B, A là UNKNOWN."""
    solver = cli.BruteForceSolver()
    kb = [(1, 2), (-1, 2)]
    assert solver.solve(kb, 2).satisfiable
    assert not solver.solve(kb, 2, (-2,)).satisfiable
    assert solver.solve(kb, 2, (1,)).satisfiable
    assert solver.solve(kb, 2, (-1,)).satisfiable


def test_e2e_bruteforce_refuses_too_many_vars():
    """E2E-13: không âm thầm chạy quá lâu."""
    with pytest.raises(ValueError):
        cli.BruteForceSolver().solve([], cli.BruteForceSolver.MAX_VARS + 1)


def test_e2e_selftest_passes_with_bruteforce_reference():
    """E2E-14: bộ selftest tự nhất quán khi chạy trên bộ giải chuẩn."""
    results = cli.run_selftest(cli.BruteForceSolver())
    assert results and all(ok for _, ok, _ in results), [r for r in results if not r[1]]


def test_e2e_selftest_passes_with_real_dpll():
    """E2E-15: DPLL của M4 qua selftest (bỏ qua nếu chưa merge)."""
    dpll = pytest.importorskip("griductive.logic.dpll")
    results = cli.run_selftest(dpll.DPLLSolver())
    assert all(ok for _, ok, _ in results), [r for r in results if not r[1]]


def test_e2e_selftest_detects_a_broken_solver():
    """E2E-16: selftest thật sự bắt được bộ giải sai (không phải kiểm tra "cho có")."""

    class AlwaysSat:
        def solve(self, clauses, num_vars, assumptions=(), timeout=None):
            return cli._Result(True, {v: True for v in range(1, num_vars + 1)})

    results = cli.run_selftest(AlwaysSat())
    assert any(not ok for _, ok, _ in results)


# --------------------------------------------------------------------------- #
# Session: kiểm model và đối chiếu chéo
# --------------------------------------------------------------------------- #
def test_e2e_session_flags_model_that_violates_a_clause():
    """E2E-17: model SAT nhưng không thỏa clause phải bị ghi nhận."""

    class BadModel:
        def solve(self, clauses, num_vars, assumptions=(), timeout=None):
            return cli._Result(True, {1: False, 2: False})

    session = cli.Session(BadModel())
    session.solve([(1, 2)], 2)
    assert session.problems and "vi phạm clause" in session.problems[0]


def test_e2e_session_flags_incomplete_model():
    """E2E-18: model thiếu biến (kiến trúc yêu cầu model đầy đủ)."""

    class Partial:
        def solve(self, clauses, num_vars, assumptions=(), timeout=None):
            return cli._Result(True, {1: True})

    session = cli.Session(Partial())
    session.solve([(1,)], 2)
    assert any("thiếu biến" in p for p in session.problems)


def test_e2e_session_cross_check_reports_disagreement():
    """E2E-19: lệch kết quả với bộ giải đối chiếu."""

    class AlwaysUnsat:
        def solve(self, clauses, num_vars, assumptions=(), timeout=None):
            return cli._Result(False, None)

    session = cli.Session(AlwaysUnsat(), cross=cli.BruteForceSolver())
    session.solve([(1,)], 1)
    assert any("LỆCH KẾT QUẢ" in p for p in session.problems)


def test_e2e_session_accumulates_call_count():
    """E2E-20: đếm số lần gọi SAT."""
    session = cli.Session(cli.BruteForceSolver())
    for _ in range(3):
        session.solve([(1,)], 1)
    assert session.totals.sat_calls == 3


# --------------------------------------------------------------------------- #
# Ranh giới thông tin: trạng thái công khai không rò rỉ
# --------------------------------------------------------------------------- #
def _fake_puzzle():
    cells = [Cell(r, c) for r in range(2) for c in range(2)]
    crim, inno = SimpleNamespace(name="CRIMINAL"), SimpleNamespace(name="INNOCENT")
    return SimpleNamespace(
        n=2,
        characters={c: object() for c in cells},
        solution={cells[0]: crim, cells[1]: inno, cells[2]: crim, cells[3]: inno},
        clues={c: f"clue-{c.row}{c.col}" for c in cells},
        initial_revealed=frozenset({cells[0]}),
    )


def _fake_public_state(**kwargs):
    return SimpleNamespace(**kwargs)


def test_iso_initial_state_contains_only_revealed_cards():
    """ISO-08: PublicState ban đầu không chứa status/clue của thẻ úp."""
    puzzle = _fake_puzzle()
    state = cli.build_initial_state(puzzle, _fake_public_state)
    assert set(state.proved) == {Cell(0, 0)}
    assert state.revealed_clues == ("clue-00",)
    assert set(state.unsolved) == {Cell(0, 1), Cell(1, 0), Cell(1, 1)}
    assert list(state.unsolved) == sorted(state.unsolved)  # row-major, xác định


def test_iso_extra_reveal_adds_only_those_cards():
    """ISO-09: ``--reveal`` chỉ lật đúng các thẻ được chỉ định."""
    puzzle = _fake_puzzle()
    state = cli.build_initial_state(puzzle, _fake_public_state, [Cell(1, 1)])
    assert set(state.proved) == {Cell(0, 0), Cell(1, 1)}
    assert state.revealed_clues == ("clue-00", "clue-11")
    assert Cell(0, 1) in state.unsolved and Cell(1, 0) in state.unsolved


# --------------------------------------------------------------------------- #
# Verdict chuẩn bằng vét cạn
# --------------------------------------------------------------------------- #
def _fake_holds(clue, assignment, n):
    kind, a, b = clue
    return (
        (assignment[a] != assignment[b])
        if kind == "DIFF"
        else (assignment[a] == assignment[b])
    )


def test_e2e_exact_verdicts_forced_and_unknown():
    """E2E-21: A1 = CRIMINAL và DIFF(A1,B1) ⇒ B1 INNOCENT; hai ô còn lại UNKNOWN."""
    a1, b1 = Cell(0, 0), Cell(0, 1)
    state = SimpleNamespace(
        proved={a1: SimpleNamespace(name="CRIMINAL")},
        revealed_clues=(("DIFF", a1, b1),),
        unsolved=(b1, Cell(1, 0), Cell(1, 1)),
    )
    verdicts = cli.exact_verdicts(state, _fake_holds, Cell, 2)
    assert verdicts[b1] == "INNOCENT"
    assert verdicts[Cell(1, 0)] == verdicts[Cell(1, 1)] == "UNKNOWN"


def test_e2e_exact_verdicts_inconsistent_returns_none():
    """E2E-22: KB vô nghiệm."""
    a1, b1 = Cell(0, 0), Cell(0, 1)
    state = SimpleNamespace(
        proved={
            a1: SimpleNamespace(name="CRIMINAL"),
            b1: SimpleNamespace(name="CRIMINAL"),
        },
        revealed_clues=(("DIFF", a1, b1),),
        unsolved=(Cell(1, 0), Cell(1, 1)),
    )
    assert cli.exact_verdicts(state, _fake_holds, Cell, 2) is None


# --------------------------------------------------------------------------- #
# main(): mã thoát và thông báo lỗi
# --------------------------------------------------------------------------- #
def test_e2e_main_cnf_mode_exit_codes(capsys):
    """E2E-23: chế độ --cnf trả mã 0 và in đúng SAT/UNSAT."""
    argv = ["--solver", "bruteforce", "--cnf", "1 2 0; -1 2 0"]
    assert cli.main(argv) == cli.EXIT_OK
    assert "DPLL   : SAT" in capsys.readouterr().out
    assert cli.main(argv + ["--assume", "-2"]) == cli.EXIT_OK
    assert "DPLL   : UNSAT" in capsys.readouterr().out


def test_e2e_main_selftest_with_bruteforce(capsys):
    """E2E-24: ``--selftest`` thoát 0 khi mọi kiểm tra đạt."""
    assert cli.main(["--solver", "bruteforce", "--selftest"]) == cli.EXIT_OK
    assert "kiểm tra đạt" in capsys.readouterr().out


def test_e2e_main_missing_module_gives_usage_exit(monkeypatch, capsys):
    """E2E-25: module chưa merge ⇒ mã 2 và thông báo chỉ rõ module/⭐ còn thiếu."""

    def boom(module, attr, owner):
        raise cli.MissingDependency(f"Chưa có `{module}.{attr}` ({owner})")

    monkeypatch.setattr(cli, "_need", boom)
    assert cli.main(["--cnf", "1 0"]) == cli.EXIT_USAGE
    assert "THIẾU MODULE" in capsys.readouterr().err


def test_e2e_main_rejects_too_small_num_vars(capsys):
    """E2E-26: ``--num-vars`` nhỏ hơn biến lớn nhất bị từ chối."""
    argv = ["--solver", "bruteforce", "--cnf", "1 5 0", "--num-vars", "3"]
    assert cli.main(argv) == cli.EXIT_USAGE


# --------------------------------------------------------------------------- #
# Đường ống đầy đủ (cần loader + encoder + DPLL + semantics thật)
# --------------------------------------------------------------------------- #
def _require_pipeline():
    for module in (
        "griductive.io.loader",
        "griductive.model.puzzle",
        "griductive.logic.encoder",
        "griductive.logic.varmap",
        "griductive.logic.semantics",
        "griductive.logic.dpll",
    ):
        pytest.importorskip(module)


def test_e2e_full_pipeline_on_demo_puzzle(capsys):
    """E2E-01: JSON → loader → encoder → DPLL, mọi kiểm tra chéo đều qua."""
    _require_pipeline()
    argv = [
        "--puzzle", str(DATA), "--check-solution", "--check-entailment",
        "--check-clues", "--brute-unique", "--cross-check",
    ]  # fmt: skip
    assert cli.main(argv) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "UNIQUE" in out and "khớp vét cạn" in out


def test_e2e_full_pipeline_sequential_encoding_same_verdicts(capsys):
    """E2E-06: hai kiểu mã hóa cho cùng verdict (bỏ qua nếu chưa có sequential)."""
    _require_pipeline()
    outputs = {}
    for encoding in ("combinatorial", "sequential"):
        try:
            code = cli.main(["--puzzle", str(DATA), "--encoding", encoding])
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"encoding {encoding} chưa hỗ trợ: {exc}")
        assert code == cli.EXIT_OK
        out = capsys.readouterr().out
        outputs[encoding] = [
            line.split()[-1] for line in out.splitlines()
            if line[:2] in {"B1", "C1", "A2", "C2", "A3", "B3", "C3"}
        ]  # fmt: skip
    assert outputs["combinatorial"] == outputs["sequential"]


def test_e2e_fuzz_matches_bruteforce(capsys):
    """E2E-07: 100 trạng thái ngẫu nhiên khớp verdict vét cạn."""
    _require_pipeline()
    assert cli.main(["--puzzle", str(DATA), "--fuzz", "100"]) == cli.EXIT_OK
    assert "khớp vét cạn" in capsys.readouterr().out


def test_e2e_json_summary_written(tmp_path, capsys):
    """E2E-08: ``--json`` ghi tóm tắt đọc lại được."""
    import json

    _require_pipeline()
    out_file = tmp_path / "summary.json"
    assert cli.main(["--puzzle", str(DATA), "--json", str(out_file)]) == cli.EXIT_OK
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["cnf"]["primary"] == 9 and data["problems"] == []
    assert set(data["verdicts"].values()) <= {"CRIMINAL", "INNOCENT", "UNKNOWN"}


# --------------------------------------------------------------------------- #
# Chịu được lệch interface so với ARCHITECTURE §5.3
# --------------------------------------------------------------------------- #
class _OldEncoder:
    def __init__(self, n):
        self.n = n


class _NewEncoder:
    def __init__(self, n, encoding="combinatorial"):
        self.args = (n, encoding)


def test_e2e_make_encoder_passes_encoding_when_supported():
    """E2E-27: encoder đúng interface nhận ``encoding``."""
    assert cli.make_encoder(_NewEncoder, 3, "sequential").args == (3, "sequential")


def test_e2e_make_encoder_tolerates_missing_encoding_param(capsys):
    """E2E-28: encoder chưa có ``encoding`` vẫn dùng được, kèm lưu ý một lần."""
    cli._NOTED.clear()
    assert cli.make_encoder(_OldEncoder, 3, "combinatorial").n == 3
    assert "lưu ý interface" in capsys.readouterr().err
    cli.make_encoder(_OldEncoder, 3, "combinatorial")
    assert capsys.readouterr().err == ""  # chỉ nhắc một lần


def test_e2e_make_encoder_refuses_unsupported_non_default_encoding():
    """E2E-29: đòi sequential mà encoder chưa hỗ trợ thì báo rõ, không âm thầm đổi."""
    with pytest.raises(cli.MissingDependency):
        cli.make_encoder(_OldEncoder, 3, "sequential")


def test_e2e_kb_info_complete_has_no_gaps():
    """E2E-30: KB đúng interface không sinh cảnh báo."""
    kb = SimpleNamespace(
        clauses=[(1, 2)], n_primary=9, n_aux=0, n_clauses=1, num_vars=9
    )
    info, gaps = cli.kb_info(kb, 3)
    assert gaps == [] and info["num_vars"] == 9


def test_e2e_kb_info_reports_missing_attributes():
    """E2E-31: KB thiếu thuộc tính ⇒ có số liệu thay thế và liệt kê từng chỗ thiếu."""
    kb = SimpleNamespace(clauses=[(1, 2), (-12, 3)])
    info, gaps = cli.kb_info(kb, 3)
    assert info == {"n_primary": 9, "n_aux": 3, "n_clauses": 2, "num_vars": 12}
    assert len(gaps) == 4
