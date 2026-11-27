"""CLI tích hợp (M1-04): JSON -> loader -> encoder -> DPLL.

Mục đích: kiểm tra bốn module do ba người viết (loader của M2, encoder của M3,
DPLL của M4) có ghép được với nhau theo interface đã đóng băng trong
``docs/ARCHITECTURE.md`` hay chưa, *trước khi* xây Engine, Agent và GUI lên trên.

Ba chế độ:

* ``--selftest``  : kiểm tra DPLL thuần bằng ví dụ trong đề (mục 3.4) và đối chiếu
  với bộ giải vét cạn. Không cần loader hay encoder.
* ``--cnf TEXT``  : giải một CNF viết tay, ví dụ ``"1 2 0; -1 2 0"``.
* ``--puzzle PATH``: đường ống đầy đủ trên một file puzzle JSON; thêm ``--fuzz N`` để
  thử N trạng thái ngẫu nhiên và so với verdict chuẩn tính bằng vét cạn.

Quy tắc kiến trúc (xem REGULATION.md mục 8):

* Trạng thái công khai ban đầu chỉ lấy clue và status của các thẻ **lật sẵn**.
  Không đọc ``solution`` của ô chưa lật để dựng KB.
* ``solution`` chỉ được đọc ở bước kiểm tra *sau cùng* khi bật ``--check-solution``
  (công cụ kiểm thử, không phải một phần của agent).

Ví dụ::

    python -m griductive.orchestration.integration_cli --selftest
    python -m griductive.orchestration.integration_cli --cnf "1 2 0; -1 2 0" --assume -2
    python -m griductive.orchestration.integration_cli \
        --puzzle puzzles/3x3_01.json --check-solution
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence

EXIT_OK = 0
EXIT_CHECK_FAILED = 1
EXIT_USAGE = 2

Clause = tuple[int, ...]


class MissingDependency(RuntimeError):
    """Một module/hàm cần thiết chưa được người phụ trách merge vào ``main``."""


def _need(module: str, attr: str, owner: str) -> Any:
    """Import ``module.attr`` hoặc báo rõ module nào còn thiếu và của ai."""
    try:
        return getattr(importlib.import_module(module), attr)
    except (ImportError, AttributeError) as exc:
        raise MissingDependency(
            f"Chưa có `{module}.{attr}` ({owner}). Chi tiết: {exc}"
        ) from exc


_NOTED: set[str] = set()


def _note_once(key: str, message: str) -> None:
    """In một lưu ý về lệch interface đúng một lần (stderr)."""
    if key not in _NOTED:
        _NOTED.add(key)
        print(f"[lưu ý interface] {message}", file=sys.stderr)


def make_encoder(encoder_cls: Any, n: int, encoding: str) -> Any:
    """Tạo ``CNFEncoder`` theo ARCHITECTURE §5.3, chịu được bản chưa có ``encoding``.

    Nếu constructor chưa nhận ``encoding`` thì dùng mặc định (combinatorial) và nhắc
    một lần; chỉ báo lỗi khi người dùng *đòi* kiểu mã hóa khác mặc định.
    """
    params = inspect.signature(encoder_cls).parameters.values()
    accepts = any(
        p.name == "encoding" or p.kind is inspect.Parameter.VAR_KEYWORD for p in params
    )
    if accepts:
        return encoder_cls(n, encoding=encoding)
    if encoding != "combinatorial":
        raise MissingDependency(
            f"CNFEncoder chưa nhận tham số `encoding` nên không dùng được "
            f"--encoding {encoding} (M3-07, ARCHITECTURE §5.3)"
        )
    _note_once(
        "encoding",
        "CNFEncoder.__init__ chưa có tham số `encoding` (ARCHITECTURE §5.3); "
        "dùng mặc định combinatorial.",
    )
    return encoder_cls(n)


def kb_info(kb: Any, n: int) -> tuple[dict[str, int], list[str]]:
    """Đọc thống kê KB; thuộc tính thiếu so với ARCHITECTURE §5.3 thì ghi thành lỗi."""
    gaps: list[str] = []
    clauses = list(kb.clauses)
    info: dict[str, int] = {}
    fallback = {
        "n_primary": n * n,
        "n_clauses": len(clauses),
        "n_aux": max([n * n] + [abs(x) for c in clauses for x in c]) - n * n,
    }
    for name in ("n_primary", "n_aux", "n_clauses"):
        if hasattr(kb, name):
            info[name] = getattr(kb, name)
        else:
            info[name] = fallback[name]
            gaps.append(f"KB thiếu thuộc tính `{name}` (ARCHITECTURE §5.3)")
    if hasattr(kb, "num_vars"):
        info["num_vars"] = kb.num_vars
    else:
        info["num_vars"] = info["n_primary"] + info["n_aux"]
        gaps.append("KB thiếu thuộc tính `num_vars` (ARCHITECTURE §5.3)")
    return info, gaps


# --------------------------------------------------------------------------- #
# Bộ giải vét cạn: chuẩn đối chiếu cho DPLL của M4 (không dùng trong luồng chính)
# --------------------------------------------------------------------------- #
@dataclass
class _Stats:
    decisions: int = 0
    propagations: int = 0
    backtracks: int = 0
    runtime: float = 0.0


@dataclass
class _Result:
    satisfiable: bool
    model: Optional[dict[int, bool]]
    stats: _Stats = field(default_factory=_Stats)


class BruteForceSolver:
    """Vét cạn mọi phép gán (tối đa ``MAX_VARS`` biến).

    Dùng làm chuẩn vàng để đối chiếu với DPLL và để chạy thử CLI khi DPLL của
    M4 chưa merge (``--solver bruteforce``). Cùng chữ ký ``solve`` với DPLL.
    """

    MAX_VARS = 18

    def solve(
        self,
        clauses: Sequence[Sequence[int]],
        num_vars: int,
        assumptions: Sequence[int] = (),
        timeout: Optional[float] = None,
    ) -> _Result:
        if num_vars > self.MAX_VARS:
            raise ValueError(
                f"Bộ giải vét cạn chỉ hỗ trợ tối đa {self.MAX_VARS} biến "
                f"(nhận {num_vars}). Dùng --solver dpll."
            )
        start = time.perf_counter()
        fixed: dict[int, bool] = {}
        for lit in assumptions:
            var, val = abs(lit), lit > 0
            if fixed.get(var, val) != val:
                return _Result(False, None, _Stats(runtime=time.perf_counter() - start))
            fixed[var] = val
        free = [v for v in range(1, num_vars + 1) if v not in fixed]
        for mask in range(1 << len(free)):
            assign = dict(fixed)
            for i, var in enumerate(free):
                assign[var] = bool((mask >> i) & 1)
            if all(any(assign[abs(x)] == (x > 0) for x in c) for c in clauses):
                return _Result(
                    True, assign, _Stats(runtime=time.perf_counter() - start)
                )
        return _Result(False, None, _Stats(runtime=time.perf_counter() - start))


# --------------------------------------------------------------------------- #
# Phiên giải: đếm số lần gọi, cộng thống kê, kiểm tra model, đối chiếu chéo
# --------------------------------------------------------------------------- #
@dataclass
class Totals:
    sat_calls: int = 0
    decisions: int = 0
    propagations: int = 0
    backtracks: int = 0
    runtime: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "sat_calls": self.sat_calls,
            "decisions": self.decisions,
            "propagations": self.propagations,
            "backtracks": self.backtracks,
            "runtime_s": round(self.runtime, 6),
        }


def model_satisfies(
    clauses: Sequence[Sequence[int]],
    assumptions: Sequence[int],
    model: Mapping[int, bool],
    num_vars: int,
) -> Optional[str]:
    """Trả ``None`` nếu model đầy đủ và thỏa clause + giả định, ngược lại lý do lỗi."""
    for var in range(1, num_vars + 1):
        if var not in model:
            return f"model thiếu biến {var} (kiến trúc yêu cầu model đầy đủ)"
    for lit in assumptions:
        if model[abs(lit)] != (lit > 0):
            return f"model vi phạm giả định {lit}"
    for index, clause in enumerate(clauses):
        if not any(model[abs(lit)] == (lit > 0) for lit in clause):
            return f"model vi phạm clause #{index}: {tuple(clause)}"
    return None


class Session:
    """Gói một bộ giải: tự kiểm model SAT, tùy chọn đối chiếu bộ giải thứ hai."""

    def __init__(
        self,
        solver: Any,
        cross: Optional[Any] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.solver = solver
        self.cross = cross
        self.timeout = timeout
        self.totals = Totals()
        self.problems: list[str] = []

    def solve(
        self,
        clauses: Sequence[Sequence[int]],
        num_vars: int,
        assumptions: Sequence[int] = (),
    ) -> Any:
        kwargs: dict[str, Any] = {}
        if self.timeout is not None:
            kwargs["timeout"] = self.timeout
        begin = time.perf_counter()
        result = self.solver.solve(clauses, num_vars, tuple(assumptions), **kwargs)
        wall = time.perf_counter() - begin

        stats = getattr(result, "stats", None)
        self.totals.sat_calls += 1
        self.totals.decisions += getattr(stats, "decisions", 0)
        self.totals.propagations += getattr(stats, "propagations", 0)
        self.totals.backtracks += getattr(stats, "backtracks", 0)
        self.totals.runtime += getattr(stats, "runtime", wall) or wall

        if result.satisfiable:
            if result.model is None:
                self.problems.append("SAT nhưng model là None")
            else:
                reason = model_satisfies(clauses, assumptions, result.model, num_vars)
                if reason:
                    self.problems.append(f"DPLL trả SAT nhưng {reason}")
        elif result.model is not None:
            self.problems.append("UNSAT nhưng model khác None")

        if self.cross is not None:
            other = self.cross.solve(clauses, num_vars, tuple(assumptions))
            if other.satisfiable != result.satisfiable:
                self.problems.append(
                    f"LỆCH KẾT QUẢ với bộ giải đối chiếu: "
                    f"assumptions={tuple(assumptions)} "
                    f"dpll={'SAT' if result.satisfiable else 'UNSAT'} "
                    f"bruteforce={'SAT' if other.satisfiable else 'UNSAT'}"
                )
        return result


# --------------------------------------------------------------------------- #
# Phân tích CNF viết tay
# --------------------------------------------------------------------------- #
def _tokens(text: str) -> list[int]:
    out: list[int] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] in "cp%":
            continue
        for tok in line.split():
            try:
                out.append(int(tok))
            except ValueError as exc:
                raise ValueError(f"Token không phải số nguyên: {tok!r}") from exc
    return out


def _split_on_zero(tokens: Sequence[int]) -> list[Clause]:
    clauses: list[Clause] = []
    current: list[int] = []
    for tok in tokens:
        if tok == 0:
            clauses.append(tuple(current))  # "0" đứng một mình = clause rỗng
            current = []
        else:
            current.append(tok)
    if current:
        clauses.append(tuple(current))
    return clauses


def parse_clauses(text: str) -> list[Clause]:
    """Phân tích CNF dạng ``"1 2 0; -1 2 0"`` hoặc DIMACS nhiều dòng.

    Dấu ``;`` ngăn cách clause (số ``0`` cuối clause là tùy chọn). Không có ``;``
    thì đọc theo DIMACS: ``0`` kết thúc clause, bỏ qua dòng ``c``/``p``.
    """
    if ";" in text:
        clauses: list[Clause] = []
        for segment in text.split(";"):
            tokens = _tokens(segment)
            if tokens:
                clauses.extend(_split_on_zero(tokens))
        return clauses
    return _split_on_zero(_tokens(text))


def _fmt_clause(clause: Sequence[int]) -> str:
    return "(" + " ∨ ".join(str(x) for x in clause) + ")" if clause else "()"


# --------------------------------------------------------------------------- #
# Chế độ --selftest
# --------------------------------------------------------------------------- #
def _brute_models_exist(clauses: Sequence[Clause], num_vars: int) -> bool:
    return BruteForceSolver().solve(clauses, num_vars).satisfiable


def run_selftest(solver: Any, verbose: bool = False) -> list[tuple[str, bool, str]]:
    """Chạy các kiểm tra DPLL thuần. Trả về danh sách (tên, đạt?, chi tiết)."""
    session = Session(solver)
    checks: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))

    # Ví dụ trong đề: KB = (A ∨ B) ∧ (¬A ∨ B), A = 1, B = 2.
    kb: list[Clause] = [(1, 2), (-1, 2)]
    record("đề: KB là SAT", session.solve(kb, 2).satisfiable)
    record(
        "đề: KB ∧ ¬B là UNSAT (⇒ KB ⊨ B, B là CRIMINAL)",
        not session.solve(kb, 2, (-2,)).satisfiable,
    )
    record("đề: KB ∧ B là SAT", session.solve(kb, 2, (2,)).satisfiable)
    record(
        "đề: KB ∧ A và KB ∧ ¬A đều SAT (⇒ A là UNKNOWN)",
        session.solve(kb, 2, (1,)).satisfiable
        and session.solve(kb, 2, (-1,)).satisfiable,
    )

    # Trường hợp biên.
    record("CNF rỗng là SAT", session.solve([], 3).satisfiable)
    record("clause rỗng là UNSAT", not session.solve([()], 1).satisfiable)
    record("(x1) ∧ (¬x1) là UNSAT", not session.solve([(1,), (-1,)], 1).satisfiable)
    record(
        "giả định mâu thuẫn (+1, -1) là UNSAT",
        not session.solve([(1, 2)], 2, (1, -1)).satisfiable,
    )
    chain: list[Clause] = [(1,), (-1, 2), (-2, 3)]
    res = session.solve(chain, 3)
    record(
        "chuỗi unit: x1 ⇒ x2 ⇒ x3",
        res.satisfiable and all(res.model[v] for v in (1, 2, 3)),
    )

    # Assumptions không được sửa clauses.
    before = [tuple(c) for c in kb]
    session.solve(kb, 2, (-2,))
    record("assumptions không sửa danh sách clause", [tuple(c) for c in kb] == before)

    # Đối chiếu ngẫu nhiên có seed cố định với vét cạn (CNF 3-SAT nhỏ).
    rng = random.Random(20261108)
    mismatches = 0
    for _ in range(150):
        n_vars = rng.randint(3, 8)
        n_clauses = rng.randint(1, 4 * n_vars)
        cnf: list[Clause] = []
        for _c in range(n_clauses):
            width = rng.randint(1, 3)
            chosen = rng.sample(range(1, n_vars + 1), min(width, n_vars))
            cnf.append(tuple(v if rng.random() < 0.5 else -v for v in chosen))
        got = session.solve(cnf, n_vars).satisfiable
        if got != _brute_models_exist(cnf, n_vars):
            mismatches += 1
            if verbose:
                print("  lệch trên CNF:", [_fmt_clause(c) for c in cnf])
    record(
        "150 CNF ngẫu nhiên (seed cố định) khớp vét cạn",
        mismatches == 0,
        f"{mismatches} ca lệch" if mismatches else "",
    )

    for problem in session.problems:
        record("model/đối chiếu hợp lệ", False, problem)
    return checks


# --------------------------------------------------------------------------- #
# Chế độ --puzzle
# --------------------------------------------------------------------------- #
def build_initial_state(
    puzzle: Any, public_state_cls: Any, extra_reveal: Sequence[Any] = ()
) -> Any:
    """Dựng ``PublicState`` ban đầu **chỉ** từ các thẻ lật sẵn.

    Status của thẻ lật sẵn là thông tin công khai; status và clue của các ô còn
    lại tuyệt đối không được đưa vào. ``extra_reveal`` (chỉ dùng cho kiểm thử, cờ
    ``--reveal``/``--fuzz``) lật thêm một số thẻ để thử nhiều loại clue hơn; những
    thẻ này vẫn chỉ đưa vào status và clue của chính chúng.
    """
    revealed = sorted(set(puzzle.initial_revealed) | set(extra_reveal))  # row-major
    clues = tuple(puzzle.clues[cell] for cell in revealed)
    proved = {cell: puzzle.solution[cell] for cell in revealed}
    unsolved = tuple(cell for cell in sorted(puzzle.characters) if cell not in proved)
    return public_state_cls(
        n=puzzle.n, revealed_clues=clues, proved=proved, unsolved=unsolved
    )


def classify_cell(
    session: Session, clauses: Sequence[Clause], num_vars: int, var: int
) -> tuple[str, str, str]:
    """Phân loại một ô bằng hai truy vấn SAT (đúng quy trình mục 3.4 của đề).

    Trả về (verdict, kết quả ``KB ∧ ¬C``, kết quả ``KB ∧ C``).
    """
    neg = session.solve(clauses, num_vars, (-var,))
    if not neg.satisfiable:
        return "CRIMINAL", "UNSAT", "-"
    pos = session.solve(clauses, num_vars, (var,))
    if not pos.satisfiable:
        return "INNOCENT", "SAT", "UNSAT"
    return "UNKNOWN", "SAT", "SAT"


def _letter(status: Any) -> str:
    return "C" if getattr(status, "name", str(status)) == "CRIMINAL" else "I"


def _grid(
    n: int, cells: Mapping[Any, str], make_cell: Callable[[int, int], Any]
) -> str:
    header = "     " + "  ".join(chr(65 + c) for c in range(n))
    lines = [header]
    for r in range(n):
        row = "  ".join(cells.get(make_cell(r, c), "?") for c in range(n))
        lines.append(f"  {r + 1}  {row}")
    return "\n".join(lines)


def exact_verdicts(
    state: Any, holds: Callable[..., bool], cell_cls: Any, n: int
) -> Optional[dict[Any, str]]:
    """Verdict chuẩn của mọi ô chưa giải, tính bằng vét cạn 2^(n²) phép gán.

    Chỉ dùng ``semantics.holds`` (đánh giá trực tiếp), không dùng encoder hay DPLL.
    Một ô là CRIMINAL/INNOCENT nếu đúng trong *mọi* model của KB; ngược lại UNKNOWN.
    Trả ``None`` nếu KB vô nghiệm.
    """
    cells = [cell_cls(r, c) for r in range(n) for c in range(n)]
    known = {cell: _letter(status) == "C" for cell, status in state.proved.items()}
    seen_true = {cell: False for cell in cells}
    seen_false = {cell: False for cell in cells}
    models = 0
    for mask in range(1 << (n * n)):
        assign = {cell: bool((mask >> i) & 1) for i, cell in enumerate(cells)}
        if any(assign[cell] != value for cell, value in known.items()):
            continue
        if not all(holds(clue, assign, n) for clue in state.revealed_clues):
            continue
        models += 1
        for cell in cells:
            (seen_true if assign[cell] else seen_false)[cell] = True
    if models == 0:
        return None
    result: dict[Any, str] = {}
    for cell in cells:
        if seen_true[cell] and not seen_false[cell]:
            result[cell] = "CRIMINAL"
        elif seen_false[cell] and not seen_true[cell]:
            result[cell] = "INNOCENT"
        else:
            result[cell] = "UNKNOWN"
    return result


def check_clue_encodings(
    puzzle: Any,
    encoder_cls: Any,
    holds: Callable[..., bool],
    cell_cls: Any,
    solver: Any,
    encoding: str,
) -> tuple[int, list[str]]:
    """Với mỗi clue, so ``semantics.holds`` với CNF trên mọi phép gán (n ≤ 3).

    ``encode(clue)`` đứng riêng phải thỏa đúng các phép gán mà ``holds`` chấp nhận
    (nếu có biến phụ thì tồn tại gán biến phụ). Bắt lỗi "thiếu một chiều" mà các kiểm
    tra trên một puzzle cụ thể có thể không thấy. Trả (số phép gán đã kiểm, lỗi).
    """
    n = puzzle.n
    cells = [cell_cls(r, c) for r in range(n) for c in range(n)]
    checked = 0
    errors: list[str] = []
    for owner, clue in sorted(puzzle.clues.items()):
        encoder = make_encoder(encoder_cls, n, encoding)
        clauses = encoder.encode(clue)
        varmap = getattr(encoder, "varmap", None)
        var_of = (
            (lambda cell: varmap.var(cell))
            if varmap
            else (lambda cell: cell.row * n + cell.col + 1)
        )
        num_vars = max([n * n] + [abs(lit) for cl in clauses for lit in cl])
        for mask in range(1 << (n * n)):
            assign = {cell: bool((mask >> i) & 1) for i, cell in enumerate(cells)}
            lits = tuple(var_of(c) if assign[c] else -var_of(c) for c in cells)
            expected = holds(clue, assign, n)
            actual = solver.solve(clauses, num_vars, lits).satisfiable
            checked += 1
            if expected != actual:
                shown = "".join("C" if assign[c] else "I" for c in cells)
                errors.append(
                    f"[clue {getattr(clue, 'id', owner)}] CNF ≠ semantics.holds: "
                    f"gán {shown}: holds={expected}, CNF={'SAT' if actual else 'UNSAT'}"
                )
                break  # một phản ví dụ cho mỗi clue là đủ
    return checked, errors


def run_puzzle(args: argparse.Namespace, solver: Any, cross: Optional[Any]) -> int:
    load_puzzle = _need("griductive.io.loader", "load_puzzle", "M2-04, mốc ⭐2")
    public_state_cls = _need("griductive.model.puzzle", "PublicState", "M2-03, mốc ⭐2")
    cell_cls = _need("griductive.model.cell", "CellId", "M2-01")
    encoder_cls = _need("griductive.logic.encoder", "CNFEncoder", "M3-03")
    varmap_cls = _need("griductive.logic.varmap", "VarMap", "M3-01")

    holds: Optional[Callable[..., bool]] = None
    if not args.no_semantic_check:
        try:
            holds = _need("griductive.logic.semantics", "holds", "M3-02")
        except MissingDependency as exc:
            print(f"[bỏ qua kiểm tra ngữ nghĩa] {exc}")

    summary: dict[str, Any] = {"puzzle": args.puzzle}
    problems: list[str] = []

    # 1. Loader
    begin = time.perf_counter()
    puzzle = load_puzzle(args.puzzle)
    n = puzzle.n
    print(
        f"Loaded : {args.puzzle} (n={n}, clues={len(puzzle.clues)}, "
        f"revealed={len(puzzle.initial_revealed)}) "
        f"[{(time.perf_counter() - begin) * 1000:.1f} ms]"
    )

    # 2. Trạng thái công khai ban đầu
    extra = [
        cell_cls.parse(text.strip()) for text in args.reveal.split(",") if text.strip()
    ]
    for cell in extra:
        if cell not in puzzle.characters:
            raise ValueError(f"--reveal: ô {cell} không có trong puzzle")
    state = build_initial_state(puzzle, public_state_cls, extra)
    if extra:
        print(f"Reveal : lật thêm {[str(c) for c in sorted(extra)]} (chỉ để kiểm thử)")
    if args.verbose:
        for clue in state.revealed_clues:
            describe = getattr(clue, "describe", lambda: repr(clue))
            print(f"  clue {getattr(clue, 'id', '?')}: {describe()}")

    # 3. Encoder
    begin = time.perf_counter()
    encoder = make_encoder(encoder_cls, n, args.encoding)
    kb = encoder.build_kb(state)
    info, gaps = kb_info(kb, n)
    num_vars = info["num_vars"]
    encode_ms = (time.perf_counter() - begin) * 1000
    print(
        f"CNF    : primary={info['n_primary']} aux={info['n_aux']} "
        f"clauses={info['n_clauses']} "
        f"encoding={args.encoding} [{encode_ms:.1f} ms]"
    )
    problems.extend(gaps)
    if info["n_primary"] != n * n:
        problems.append(f"n_primary={info['n_primary']} nhưng kỳ vọng {n * n}")
    if num_vars != info["n_primary"] + info["n_aux"]:
        problems.append("num_vars khác n_primary + n_aux")
    summary["cnf"] = {
        "primary": info["n_primary"],
        "aux": info["n_aux"],
        "clauses": info["n_clauses"],
        "encoding": args.encoding,
    }

    varmap = getattr(encoder, "varmap", None) or varmap_cls(n)

    session = Session(solver, cross, args.timeout)

    # 4. Nhất quán của KB
    base = session.solve(kb.clauses, num_vars)
    base_stats = getattr(base, "stats", None)
    print(
        f"DPLL   : {'SAT' if base.satisfiable else 'UNSAT'} "
        f"decisions={getattr(base_stats, 'decisions', 0)} "
        f"propagations={getattr(base_stats, 'propagations', 0)} "
        f"backtracks={getattr(base_stats, 'backtracks', 0)} "
        f"runtime={getattr(base_stats, 'runtime', 0.0) * 1000:.2f} ms"
    )
    summary["kb_sat"] = bool(base.satisfiable)

    verdicts: dict[Any, str] = {}
    if not base.satisfiable:
        print("KB     : INCONSISTENT (KB không có model). Không phân loại ô nào.")
        summary["state"] = "INCONSISTENT"
    else:
        # 5. Kiểm tra chéo bằng evaluator ngữ nghĩa độc lập với encoder
        primary_vars = [varmap.var(cell_cls(r, c)) for r in range(n) for c in range(n)]
        model_ok = base.model is not None and all(v in base.model for v in primary_vars)
        if holds is not None and not model_ok:
            print(
                "Check  : bỏ qua kiểm tra ngữ nghĩa vì model của DPLL thiếu biến chính"
            )
        if holds is not None and model_ok:
            problems_before = len(problems)
            assignment = {
                cell_cls(r, c): base.model[varmap.var(cell_cls(r, c))]
                for r in range(n)
                for c in range(n)
            }
            for clue in state.revealed_clues:
                if not holds(clue, assignment, n):
                    problems.append(
                        f"Model của DPLL vi phạm clue {getattr(clue, 'id', '?')} "
                        f"theo semantics.holds (encoder hoặc DPLL sai)"
                    )
            for cell, status in state.proved.items():
                if assignment[cell] != (_letter(status) == "C"):
                    problems.append(f"Model mâu thuẫn status đã biết của {cell}")
            if len(problems) == problems_before:
                print(
                    "Check  : model của DPLL thỏa mọi clue đã lộ theo semantics.holds"
                )
            else:
                print("Check  : CÓ LỖI (xem cuối)")

        # 6. Phân loại các ô chưa giải bằng hai truy vấn SAT
        print("\nCell  KB∧¬C   KB∧C    Verdict")
        for cell in state.unsolved:
            var = varmap.var(cell)
            verdict, q_neg, q_pos = classify_cell(session, kb.clauses, num_vars, var)
            verdicts[cell] = verdict
            print(f"{str(cell):<5} {q_neg:<7} {q_pos:<7} {verdict}")
        forced = {c: v for c, v in verdicts.items() if v != "UNKNOWN"}
        print(
            f"\nTổng   : {len(forced)}/{len(state.unsolved)} ô được suy ra, "
            f"{len(state.unsolved) - len(forced)} ô UNKNOWN"
        )

        marks: dict[Any, str] = {}
        for cell in state.proved:
            marks[cell] = _letter(state.proved[cell]).lower()
        for cell, verdict in verdicts.items():
            marks[cell] = {"CRIMINAL": "C", "INNOCENT": "I"}.get(verdict, ".")
        print("\nLưới (c/i = thẻ lật sẵn, C/I = được suy ra, . = UNKNOWN):")
        print(_grid(n, marks, cell_cls))

        summary["state"] = "OK"
        summary["verdicts"] = {str(c): v for c, v in verdicts.items()}

        # 7. Kiểm tra bằng đáp án: CHỈ là công cụ kiểm thử
        if args.check_solution:
            print(
                "\n[--check-solution] đọc solution để kiểm thử (không dùng để suy diễn)"
            )
            if holds is not None:
                truth = {
                    cell: _letter(puzzle.solution[cell]) == "C"
                    for cell in puzzle.solution
                }
                for cell, clue in puzzle.clues.items():
                    if not holds(clue, truth, n):
                        problems.append(
                            f"Đáp án trong file KHÔNG thỏa clue của thẻ {cell} "
                            f"(dữ liệu puzzle sai)"
                        )
            for cell, verdict in forced.items():
                expected = (
                    "CRIMINAL" if _letter(puzzle.solution[cell]) == "C" else "INNOCENT"
                )
                if verdict != expected:
                    problems.append(
                        f"Verdict suy ra cho {cell} là {verdict} nhưng đáp án là "
                        f"{expected} "
                        f"(suy diễn không đúng đắn!)"
                    )

    # 7b. Verdict chuẩn bằng vét cạn: bắt cả encoder "sai" lẫn encoder "thiếu ràng buộc"
    if args.check_entailment:
        if holds is None:
            print("[--check-entailment] cần semantics.holds (M3-02)")
        elif n > 4:
            print("[--check-entailment] chỉ hỗ trợ n ≤ 4")
        else:
            reference = exact_verdicts(state, holds, cell_cls, n)
            if reference is None:
                print("[--check-entailment] KB vô nghiệm theo vét cạn (INCONSISTENT)")
                if base.satisfiable:
                    problems.append("Vét cạn: KB vô nghiệm nhưng DPLL báo SAT")
            else:
                diffs = [
                    f"{cell}: CLI={verdicts.get(cell)} nhưng vét cạn={reference[cell]}"
                    for cell in state.unsolved
                    if verdicts.get(cell) != reference[cell]
                ]
                if not base.satisfiable:
                    diffs.append("CLI báo INCONSISTENT nhưng vét cạn có model")
                if diffs:
                    problems.extend(f"[entailment] {d}" for d in diffs)
                    print(f"[--check-entailment] LỆCH {len(diffs)} ô")
                else:
                    print(
                        f"[--check-entailment] khớp vét cạn trên "
                        f"{len(state.unsolved)} ô "
                        f"(encoder đủ và đúng trên puzzle này)"
                    )

    # 7c. Từng clue: CNF so với semantics trên mọi phép gán
    if args.check_clues:
        if holds is None:
            print("[--check-clues] cần semantics.holds (M3-02)")
        elif n > 3:
            print("[--check-clues] chỉ hỗ trợ n ≤ 3 (512 phép gán mỗi clue)")
        else:
            checked, errors = check_clue_encodings(
                puzzle, encoder_cls, holds, cell_cls, solver, args.encoding
            )
            if errors:
                problems.extend(errors)
                print(
                    f"[--check-clues] {len(errors)}/{len(puzzle.clues)} clue có CNF sai"
                )
            else:
                print(
                    f"[--check-clues] CNF khớp semantics.holds trên {checked} phép gán "
                    f"({len(puzzle.clues)} clue × 2^{n * n})"
                )

    # 8. Đếm model bằng vét cạn (M2 kiểm tạm tính duy nhất; M5 sẽ có bản chính thức)
    if args.brute_unique:
        if holds is None:
            print("[--brute-unique] cần semantics.holds (M3-02)")
        elif n > 4:
            print("[--brute-unique] chỉ hỗ trợ n ≤ 4")
        else:
            count = 0
            for mask in range(1 << (n * n)):
                asg = {
                    cell_cls(i // n, i % n): bool((mask >> i) & 1) for i in range(n * n)
                }
                if all(holds(c, asg, n) for c in puzzle.clues.values()):
                    count += 1
                    if count > 1:
                        break
            label = {0: "UNSAT (vô nghiệm)", 1: "UNIQUE"}.get(
                count, "NOT_UNIQUE (≥ 2 lời giải)"
            )
            print(f"[--brute-unique] toàn bộ clue: {label}")
            summary["brute_unique"] = label

    problems.extend(session.problems)
    summary["totals"] = session.totals.as_dict()
    totals = session.totals
    print(
        f"\nSAT    : calls={totals.sat_calls} decisions={totals.decisions} "
        f"propagations={totals.propagations} backtracks={totals.backtracks} "
        f"runtime={totals.runtime * 1000:.2f} ms"
    )

    summary["problems"] = problems
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, ensure_ascii=False, indent=2)
        print(f"Đã ghi {args.json}")

    if problems:
        print("\nPHÁT HIỆN LỖI TÍCH HỢP:")
        for item in problems:
            print(f"  - {item}")
        return EXIT_CHECK_FAILED
    print("\nOK: đường ống JSON → loader → encoder → DPLL chạy thông suốt.")
    return EXIT_OK


def run_fuzz(args: argparse.Namespace, solver: Any, cross: Optional[Any]) -> int:
    """Thử ``--fuzz N`` trạng thái công khai ngẫu nhiên (seed cố định) trên một puzzle.

    Mỗi lần: lật một tập thẻ ngẫu nhiên, mã hóa, phân loại mọi ô bằng DPLL, rồi so với
    verdict chuẩn tính bằng vét cạn qua ``semantics.holds``. Phát hiện cả encoder
    "sai" (suy ra sai) lẫn encoder "yếu" (bỏ sót ràng buộc, suy ra thiếu).
    """
    load_puzzle = _need("griductive.io.loader", "load_puzzle", "M2-04, mốc ⭐2")
    public_state_cls = _need("griductive.model.puzzle", "PublicState", "M2-03, mốc ⭐2")
    cell_cls = _need("griductive.model.cell", "CellId", "M2-01")
    encoder_cls = _need("griductive.logic.encoder", "CNFEncoder", "M3-03")
    varmap_cls = _need("griductive.logic.varmap", "VarMap", "M3-01")
    holds = _need("griductive.logic.semantics", "holds", "M3-02")

    puzzle = load_puzzle(args.puzzle)
    n = puzzle.n
    if n > 4:
        print("--fuzz chỉ hỗ trợ n ≤ 4 (vét cạn 2^(n²))", file=sys.stderr)
        return EXIT_USAGE
    cells = sorted(puzzle.characters)
    rng = random.Random(args.seed)
    session = Session(solver, cross, args.timeout)
    problems: list[str] = []
    forced_total = inconsistent = 0
    seen_gaps: set[str] = set()

    for trial in range(args.fuzz):
        size = rng.randint(1, max(1, len(cells) - 2))
        chosen = rng.sample(cells, size)
        state = build_initial_state(puzzle, public_state_cls, chosen)
        # encoder mới mỗi lần: biến phụ tính lại từ đầu
        encoder = make_encoder(encoder_cls, n, args.encoding)
        kb = encoder.build_kb(state)
        info, gaps = kb_info(kb, n)
        num_vars = info["num_vars"]
        for gap in gaps:
            if gap not in seen_gaps:
                seen_gaps.add(gap)
                problems.append(gap)
        varmap = getattr(encoder, "varmap", None) or varmap_cls(n)
        reference = exact_verdicts(state, holds, cell_cls, n)
        base = session.solve(kb.clauses, num_vars)
        label = f"trial {trial} reveal={[str(c) for c in sorted(chosen)]}"
        if reference is None or not base.satisfiable:
            inconsistent += 1
            if (reference is None) != (not base.satisfiable):
                problems.append(
                    f"{label}: INCONSISTENT lệch (vét cạn={reference is None}, "
                    f"DPLL={not base.satisfiable})"
                )
            continue
        for cell in state.unsolved:
            verdict, _, _ = classify_cell(
                session, kb.clauses, num_vars, varmap.var(cell)
            )
            forced_total += verdict != "UNKNOWN"
            if verdict != reference[cell]:
                problems.append(
                    f"{label}: ô {cell} CLI={verdict} nhưng vét cạn={reference[cell]}"
                )

    problems.extend(session.problems)
    print(
        f"Fuzz   : {args.fuzz} trạng thái (seed={args.seed}), "
        f"{forced_total} verdict được suy ra, "
        f"{inconsistent} trạng thái INCONSISTENT"
    )
    t = session.totals
    print(
        f"SAT    : calls={t.sat_calls} decisions={t.decisions} "
        f"propagations={t.propagations} backtracks={t.backtracks}"
    )
    if problems:
        print(f"\nPHÁT HIỆN {len(problems)} LỖI TÍCH HỢP (hiển thị tối đa 10):")
        for item in problems[:10]:
            print(f"  - {item}")
        return EXIT_CHECK_FAILED
    print("\nOK: encoder + DPLL khớp vét cạn trên mọi trạng thái đã thử.")
    return EXIT_OK


# --------------------------------------------------------------------------- #
# Chế độ --cnf
# --------------------------------------------------------------------------- #
def run_cnf(args: argparse.Namespace, solver: Any, cross: Optional[Any]) -> int:
    clauses = parse_clauses(args.cnf)
    highest = max((abs(x) for c in clauses for x in c), default=0)
    highest = max([highest] + [abs(a) for a in args.assume])
    num_vars = max(highest, args.num_vars or 0)
    if args.num_vars is not None and args.num_vars < highest:
        print(
            f"--num-vars={args.num_vars} nhỏ hơn biến lớn nhất {highest}",
            file=sys.stderr,
        )
        return EXIT_USAGE

    print(f"CNF    : {len(clauses)} clause, {num_vars} biến")
    for clause in clauses:
        print("  ", _fmt_clause(clause))
    if args.assume:
        print(f"Giả định: {list(args.assume)}")

    session = Session(solver, cross, args.timeout)
    result = session.solve(clauses, num_vars, tuple(args.assume))
    stats = getattr(result, "stats", None)
    print(
        f"DPLL   : {'SAT' if result.satisfiable else 'UNSAT'} "
        f"decisions={getattr(stats, 'decisions', 0)} "
        f"propagations={getattr(stats, 'propagations', 0)} "
        f"backtracks={getattr(stats, 'backtracks', 0)}"
    )
    if result.satisfiable and result.model:
        print(
            "Model  :",
            " ".join(
                f"x{v}={'T' if result.model[v] else 'F'}" for v in sorted(result.model)
            ),
        )
    for problem in session.problems:
        print("LỖI:", problem)
    return EXIT_CHECK_FAILED if session.problems else EXIT_OK


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="integration_cli",
        description="CLI tích hợp: JSON -> loader -> encoder -> DPLL (M1-04).",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--puzzle", metavar="PATH", help="file puzzle JSON")
    mode.add_argument("--cnf", metavar="TEXT", help='CNF thô, ví dụ "1 2 0; -1 2 0"')
    mode.add_argument(
        "--selftest", action="store_true", help="kiểm tra DPLL bằng ví dụ trong đề"
    )
    parser.add_argument(
        "--assume", type=int, nargs="*", default=[], help="literal giả định cho --cnf"
    )
    parser.add_argument(
        "--num-vars", type=int, help="số biến (mặc định: biến lớn nhất trong CNF)"
    )
    parser.add_argument(
        "--encoding", choices=["combinatorial", "sequential"], default="combinatorial"
    )
    parser.add_argument(
        "--solver",
        choices=["dpll", "bruteforce"],
        default="dpll",
        help="bruteforce: chạy thử CLI khi DPLL của M4 chưa có (≤ 18 biến)",
    )
    parser.add_argument(
        "--cross-check",
        action="store_true",
        help="đối chiếu mọi truy vấn với bộ giải vét cạn (≤ 18 biến)",
    )
    parser.add_argument(
        "--timeout", type=float, help="timeout (giây) cho mỗi lần gọi solve"
    )
    parser.add_argument(
        "--check-solution",
        action="store_true",
        help="[kiểm thử] đối chiếu verdict với solution trong file",
    )
    parser.add_argument(
        "--brute-unique",
        action="store_true",
        help="[kiểm thử] đếm model toàn bộ clue bằng vét cạn (n ≤ 4)",
    )
    parser.add_argument(
        "--check-entailment",
        action="store_true",
        help="[kiểm thử] tính verdict chuẩn bằng vét cạn qua semantics.holds "
        "(độc lập encoder và DPLL), so với kết quả của CLI (n ≤ 4)",
    )
    parser.add_argument(
        "--check-clues",
        action="store_true",
        help="[kiểm thử] từng clue: CNF so với semantics.holds mọi phép gán (n ≤ 3)",
    )
    parser.add_argument(
        "--reveal",
        default="",
        metavar="A1,B2",
        help="[kiểm thử] lật thêm các thẻ này ngay từ đầu",
    )
    parser.add_argument(
        "--fuzz",
        type=int,
        metavar="N",
        help="[kiểm thử] thử N trạng thái ngẫu nhiên, so với vét cạn (n ≤ 4)",
    )
    parser.add_argument("--seed", type=int, default=20261108, help="seed cho --fuzz")
    parser.add_argument(
        "--no-semantic-check",
        action="store_true",
        help="bỏ kiểm tra model bằng semantics.holds",
    )
    parser.add_argument("--json", metavar="PATH", help="ghi tóm tắt kết quả ra JSON")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.solver == "bruteforce":
            solver: Any = BruteForceSolver()
        else:
            solver = _need("griductive.logic.dpll", "DPLLSolver", "M4-01, mốc ⭐3")()
        cross: Optional[Any] = BruteForceSolver() if args.cross_check else None

        if args.selftest:
            checks = run_selftest(solver, args.verbose)
            for name, ok, detail in checks:
                print(
                    f"[{'PASS' if ok else 'FAIL'}] {name}"
                    + (f" ({detail})" if detail else "")
                )
            failed = sum(1 for _, ok, _ in checks if not ok)
            print(f"\n{len(checks) - failed}/{len(checks)} kiểm tra đạt")
            return EXIT_CHECK_FAILED if failed else EXIT_OK
        if args.cnf is not None:
            return run_cnf(args, solver, cross)
        if args.fuzz:
            return run_fuzz(args, solver, cross)
        return run_puzzle(args, solver, cross)
    except MissingDependency as exc:
        print(f"THIẾU MODULE: {exc}", file=sys.stderr)
        print(
            "Gợi ý: kiểm tra mốc ⭐ trong docs/TASKS.md, hoặc thêm --solver bruteforce.",
            file=sys.stderr,
        )
        return EXIT_USAGE
    except (OSError, ValueError) as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except Exception as exc:  # noqa: BLE001 - chỉ bắt các lỗi nghiệp vụ đã biết
        if type(exc).__name__ in {"PuzzleError", "ClueError", "SolverTimeout"}:
            print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
            return EXIT_USAGE
        raise


if __name__ == "__main__":
    sys.exit(main())
