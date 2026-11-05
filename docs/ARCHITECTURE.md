# ARCHITECTURE.md

Tài liệu kiến trúc và **hợp đồng interface** của Griductive Solver.
Mọi thay đổi interface phải qua **đề xuất → Leader duyệt → thông báo cả nhóm**.

- Trạng thái: `DRAFT` → `FROZEN` (Quang cập nhật)
- Chủ sở hữu tài liệu: Quang

---

## 1. Nguyên tắc kiến trúc (bất khả xâm phạm)

| # | Nguyên tắc | Cách kiểm tra |
|---|---|---|
| P1 | **Logic Agent chỉ thấy `PublicState`.** Không import `engine/`, không đọc `Puzzle.solution`, không đọc clue chưa lộ | Test `test_agent_isolation`: quét import trong `logic/`; CI fail nếu có `griductive.engine` |
| P2 | **Game Engine không dùng `solution` để chấp nhận/từ chối verdict.** Engine hỏi oracle suy diễn (SAT). `solution` chỉ dùng khi load (kiểm tra nhất quán) và để báo "solved" | Review code `submit` |
| P3 | **Không viết tay CNF theo puzzle.** Mọi clue đi qua `CNFEncoder` | Review; không có file CNF cố định trong repo |
| P4 | **DPLL tự cài đặt**, không dùng thư viện SAT | `requirements.txt` không có `pysat`, `z3`, ... |
| P5 | **Một nguồn sự thật cho "vùng".** Encoder, evaluator và GUI đều dùng `RegionResolver.cells()` | Không có code tự tính neighbors ở nơi khác |
| P6 | **Evaluator độc lập với encoder.** `semantics.holds` không import `encoder` | Test đối chiếu `semantics = CNF` |
| P7 | **Biến chính và biến phụ tách biệt.** Biến chính `1..N²`, biến phụ từ `N²+1` | `VarMap` |
| P8 | **Xác định (deterministic).** Cùng input cho cùng output: row-major, không dùng `random`/set order | Test chạy hai lần so sánh trace |

---

## 2. Sơ đồ tổng thể

```
                 ┌─────── GUI / CLI / Experiments ────────┐
                 │                                        │
                 ▼                                        ▼
        ┌─────────────────┐   public_state()    ┌───────────────────┐
        │   GameEngine    │ ──────────────────► │  Orchestration    │
        │ (M2)            │ ◄────────────────── │  runner_loop (M5) │
        │ solution, clues │   submit(cell,st)   └─────────┬─────────┘
        └───────┬─────────┘                               │ next_forced(state) / hint(state)
                │ oracle(state, cell) (inject)            ▼
                │                                 ┌───────────────┐
                └────────────────────────────────►│  LogicAgent   │ (M4)
                                                  │  entailment   │
                                                  └───────┬───────┘
                                                          │ build_kb(state)
                                                          ▼
                                                  ┌───────────────┐      ┌───────────────┐
                                                  │  CNFEncoder   │ ───► │  DPLLSolver   │
                                                  │  (M3)         │      │  (M4)         │
                                                  └───────────────┘      └───────────────┘
```

**Ranh giới thông tin:** chỉ `PublicState` đi từ Engine sang phía logic.

| Thành phần | Được thấy | Không được thấy |
|---|---|---|
| `GameEngine` | Toàn bộ `Puzzle` | (không giới hạn) |
| `LogicAgent`, `CNFEncoder`, `DPLLSolver` | `PublicState` (clue đã lộ, verdict đã chứng minh, `n`) | `solution`, clue úp, tên và nghề (không mang logic) |
| GUI | Kết quả từ engine (trạng thái hiển thị) | `solution` (chỉ engine biết) |

**Injection:** `main.py` tạo `LogicAgent`, rồi truyền `agent.classify` vào `GameEngine(puzzle, oracle=agent.classify)`. Engine chỉ biết một hàm callable, không biết lớp `LogicAgent`.

**Quy tắc phụ thuộc import (một chiều):**

```
model  ←  io
model  ←  logic   (varmap, semantics, cardinality, encoder, dpll, entailment, agent, uniqueness, trace)
model  ←  engine
engine, logic  ←  orchestration  ←  gui, experiments  ←  main.py
```

`logic/` **không** import `engine/`. `engine/` **không** import `logic/`. Chỉ `orchestration/` và `main.py` biết cả hai.

---

## 3. Cấu trúc thư mục và chủ sở hữu

| Đường dẫn | Chủ sở hữu | Nội dung |
|---|:---:|---|
| `docs/`, `main.py`, `tests/` (khung) | M1 | tài liệu, entry point, CI |
| `griductive/model/` | M2 | `cell.py`, `region.py`, `clue.py`, `puzzle.py` |
| `griductive/io/loader.py` | M2 | JSON → `Puzzle`, validate |
| `griductive/engine/game_engine.py` | M2 | `GameEngine`, `VerdictResult` |
| `puzzles/` | M2 | bộ puzzle chuẩn, lỗi, stress |
| `griductive/logic/varmap.py`, `semantics.py`, `cardinality.py`, `encoder.py` | M3 | CNF |
| `griductive/logic/dpll.py`, `entailment.py`, `agent.py` | M4 | SAT, suy diễn |
| `griductive/logic/uniqueness.py`, `trace.py` | M5 | duy nhất, trace |
| `griductive/orchestration/runner_loop.py` | M5 | vòng lặp suy diễn (generator) |
| `griductive/gui/` | M5 | Tkinter |
| `griductive/experiments/` | M5 | runner, bảng, biểu đồ |

Mỗi người viết unit test cho module mình sở hữu trong `tests/`.

---

## 4. Mô hình dữ liệu (`model/`, M2)

Mọi dataclass đều `frozen=True` (bất biến, hashable), có type hints.

### 4.1 Ô và trạng thái

```python
class Status(Enum):
    CRIMINAL = "CRIMINAL"
    INNOCENT = "INNOCENT"

@dataclass(frozen=True, order=True)
class CellId:
    row: int      # 0-based, từ trên xuống
    col: int      # 0-based, từ trái sang
    # str(CellId(1, 2)) == "C2"  (cột C, hàng 2)
    @staticmethod
    def parse(text: str) -> "CellId": ...     # "C2" -> CellId(1, 2)

@dataclass(frozen=True)
class Character:
    cell: CellId
    name: str
    job: str          # chỉ để hiển thị, không mang ý nghĩa logic
```

`order=True` cho thứ tự **row-major** (dùng cho mọi lựa chọn xác định).

### 4.2 Vùng

```python
class RegionKind(Enum):
    ROW = "ROW"
    COL = "COL"
    NEIGHBORS = "NEIGHBORS"
    CELLS = "CELLS"

@dataclass(frozen=True)
class Region:
    kind: RegionKind
    row: int | None = None            # ROW (0-based)
    col: int | None = None            # COL (0-based)
    center: CellId | None = None      # NEIGHBORS
    cells: tuple[CellId, ...] = ()    # CELLS (phân biệt, không trùng)

class RegionResolver:
    @staticmethod
    def cells(region: Region, n: int) -> tuple[CellId, ...]:
        """Danh sách ô của vùng, đã sắp xếp row-major, không trùng.
        NEIGHBORS: 8 hướng, loại chính ô center, cắt theo biên lưới."""
```

**Đây là nơi duy nhất định nghĩa nghĩa của vùng (P5).**

### 4.3 Clue

```python
class Clue(ABC):
    id: str                                    # ví dụ "clue@A1" (clue của thẻ A1)
    @abstractmethod
    def cells(self, n: int) -> tuple[CellId, ...]: ...   # ô được nhắc tới/đếm (GUI highlight)
    @abstractmethod
    def describe(self) -> str: ...                       # câu hiển thị
```

| Lớp | Trường | Logic |
|---|---|---|
| `Fact` | `cell`, `status` | `Cᵢ` hoặc `¬Cᵢ` |
| `Same` | `a`, `b` | `Cₐ ↔ C_b` |
| `Different` | `a`, `b` | `Cₐ ⊕ C_b` |
| `Count` | `op: "EQ" \| "GE" \| "LE"`, `k`, `region` | `Σ C = k`, `≥ k`, `≤ k` |
| `Parity` *(extension)* | `region`, `parity: "EVEN" \| "ODD"` | `Σ C ≡ 0` hoặc `1 (mod 2)` |
| `Compare` *(extension)* | `left: Region`, `op: "LT" \| "LE" \| "EQ" \| "GE" \| "GT"`, `right: Region` | `Σ_left C  op  Σ_right C` |

`EXACTLY(0, R)` biểu diễn bằng `Count(op="EQ", k=0)` ("NO").
Ràng buộc: `0 ≤ k ≤ |R|`; vùng không rỗng; ô tồn tại. Loader validate các điều này.

### 4.4 Puzzle và PublicState

```python
@dataclass(frozen=True)
class Puzzle:                         # CHỈ GameEngine giữ
    n: int
    characters: Mapping[CellId, Character]
    solution: Mapping[CellId, Status]
    clues: Mapping[CellId, Clue]      # clue gắn với thẻ của ô đó
    initial_revealed: frozenset[CellId]

@dataclass(frozen=True)
class PublicState:                    # DUY NHẤT thứ logic được thấy
    n: int
    revealed_clues: tuple[Clue, ...]               # theo thứ tự lộ, xác định
    proved: Mapping[CellId, Status]                # verdict đã chứng minh (kể cả thẻ lật sẵn)
    unsolved: tuple[CellId, ...]                   # row-major
```

Mọi mảng/dict trong `PublicState` phải **sắp xếp xác định** (P8).

---

## 5. Tầng logic (`logic/`)

### 5.1 Quy ước CNF

- Một **literal** là `int` khác 0: `+v` là biến `v` đúng, `-v` là phủ định (kiểu DIMACS).
- Một **clause** là `tuple[int, ...]`; một **CNF** là `list[Clause]`.
- Biến chính: `var(CellId(r, c)) = r * N + c + 1` (từ `1` đến `N²`).
- Biến phụ: từ `N² + 1` trở lên, cấp bằng `VarMap.new_aux()`.

```python
class VarMap:
    def __init__(self, n: int): ...
    def var(self, cell: CellId) -> int
    def cell(self, var: int) -> CellId          # chỉ cho biến chính
    def new_aux(self) -> int
    @property
    def n_primary(self) -> int
    @property
    def n_aux(self) -> int
```

### 5.2 Evaluator ngữ nghĩa (M3) — `semantics.py`

```python
def holds(clue: Clue, assignment: Mapping[CellId, bool], n: int) -> bool
```

Đánh giá clue trên một assignment đầy đủ, **không gọi encoder** (P6). Dùng làm "chuẩn vàng" để test encoder.

### 5.3 Encoder (M3) — `encoder.py`

```python
@dataclass
class KB:
    clauses: list[tuple[int, ...]]
    n_primary: int
    n_aux: int
    @property
    def n_clauses(self) -> int: ...
    @property
    def num_vars(self) -> int: ...             # n_primary + n_aux

class CNFEncoder:
    def __init__(self, n: int, encoding: Literal["combinatorial", "sequential"] = "combinatorial"): ...
    def encode(self, clue: Clue) -> list[tuple[int, ...]]
    def build_kb(self, state: PublicState) -> KB
        # KB_t = CNF(revealed_clues) ∧ unit clauses cho state.proved
```

- Validate tham số clue; lỗi → `ClueError`.
- Nếu `encoding="combinatorial"` mà vùng quá lớn (ngưỡng cấu hình, ví dụ `C(|R|, k+1) > 50 000`), tự chuyển sang `sequential` và ghi cảnh báo.
- Công thức chi tiết: [`CNF_MAPPING.md`](CNF_MAPPING.md).

### 5.4 DPLL (M4) — `dpll.py`

```python
@dataclass
class SolverStats:
    decisions: int = 0
    propagations: int = 0
    backtracks: int = 0
    runtime: float = 0.0          # giây

@dataclass
class SolveResult:
    satisfiable: bool
    model: dict[int, bool] | None  # đầy đủ mọi biến 1..num_vars nếu SAT
    stats: SolverStats

class DPLLSolver:
    def solve(self,
              clauses: Sequence[Sequence[int]],
              num_vars: int,
              assumptions: Sequence[int] = (),
              timeout: float | None = None) -> SolveResult
```

- `assumptions` coi như unit clause **tạm thời**, không sửa `clauses`.
- Chọn biến: **biến chưa gán có chỉ số nhỏ nhất**, thử `True` rồi `False` (P8).
- Bắt buộc: unit propagation, phát hiện xung đột, backtracking. Pure-literal: tùy chọn (bật bằng cờ).
- `timeout` quá hạn → raise `SolverTimeout` (runner ghi `TIMEOUT`).

### 5.5 Entailment và Agent (M4) — `entailment.py`, `agent.py`

```python
class Verdict(Enum):
    CRIMINAL = "CRIMINAL"
    INNOCENT = "INNOCENT"
    UNKNOWN = "UNKNOWN"
    INCONSISTENT = "INCONSISTENT"

@dataclass(frozen=True)
class SatQueryRecord:
    cell: CellId | None            # None khi kiểm tra tính nhất quán của KB
    assumption: int | None         # literal giả định (+v / -v) hoặc None
    satisfiable: bool
    stats: SolverStats

@dataclass(frozen=True)
class Classification:
    verdict: Verdict
    queries: tuple[SatQueryRecord, ...]

def classify(kb: KB, varmap: VarMap, cell: CellId, solver: DPLLSolver) -> Classification
```

Quy trình `classify`:

1. `SAT(KB)` sai → `INCONSISTENT`.
2. `SAT(KB ∧ ¬Cᵢ)` sai → `CRIMINAL`.
3. `SAT(KB ∧ Cᵢ)` sai → `INNOCENT`.
4. Còn lại → `UNKNOWN`.

```python
class LogicAgent:
    def __init__(self, encoder_factory=..., solver_factory=...): ...
    def classify(self, state: PublicState, cell: CellId) -> Classification   # oracle cho engine
    def classify_all(self, state: PublicState) -> dict[CellId, Classification]
    def next_forced(self, state: PublicState) -> tuple[CellId, Verdict] | None
        # ô forced đầu tiên theo row-major; None nếu không có
    def hint(self, state: PublicState) -> Hint
        # ô forced + clue đã lộ liên quan; KHÔNG đọc solution
```

```python
@dataclass(frozen=True)
class Hint:
    cell: CellId
    verdict: Verdict
    related_clue_ids: tuple[str, ...]    # clue đã lộ có chứa cell trong cells()
    queries: tuple[SatQueryRecord, ...]
```

### 5.6 Tính duy nhất (M5) — `uniqueness.py`

```python
@dataclass(frozen=True)
class UniquenessReport:
    status: Literal["UNIQUE", "NOT_UNIQUE", "UNSAT"]
    models_found: int                 # 0, 1 hoặc 2
    models: tuple[Mapping[CellId, Status], ...]
    stats: SolverStats

def check_uniqueness(clues: Sequence[Clue], n: int, solver: DPLLSolver, encoder: CNFEncoder) -> UniquenessReport
```

Kiểm tra trên **toàn bộ clue của puzzle** (kể cả clue chưa lộ, nên hàm này là công cụ riêng, không nằm trong luồng của agent). Tìm một model, thêm blocking clause (chỉ trên biến chính), tìm tiếp; dừng khi đủ 2 model.

### 5.7 Trace (M5) — `trace.py`

```python
@dataclass(frozen=True)
class TraceStep:
    step: int                                     # bắt đầu từ 1
    active_clue_ids: tuple[str, ...]
    sat_queries: tuple[SatQueryRecord, ...]
    verdict: tuple[CellId, Status]
    revealed_clue_id: str | None

class TraceLog:
    steps: list[TraceStep]
    terminal: Literal["SOLVED", "STUCK", "INCONSISTENT", "ERROR"]
    def to_json(self) -> str: ...
    def to_csv(self) -> str: ...
```

---

## 6. Game Engine (`engine/`, M2)

```python
class VerdictOutcome(Enum):
    ACCEPTED = "ACCEPTED"
    NOT_PROVABLE = "NOT_PROVABLE"
    CONTRADICTED = "CONTRADICTED"
    INCONSISTENT = "INCONSISTENT"

@dataclass(frozen=True)
class VerdictResult:
    outcome: VerdictOutcome
    cell: CellId
    revealed_clue: Clue | None            # chỉ có khi ACCEPTED
    queries: tuple[SatQueryRecord, ...]   # để trace/GUI hiển thị

Oracle = Callable[[PublicState, CellId], Classification]

class GameEngine:
    def __init__(self, puzzle: Puzzle, oracle: Oracle): ...
    def public_state(self) -> PublicState
    def submit(self, cell: CellId, status: Status) -> VerdictResult
    def is_solved(self) -> bool
    def restart(self) -> None
    @classmethod
    def load(cls, path: str, oracle: Oracle) -> "GameEngine"
```

Logic `submit(cell, status)`:

```
state = public_state()
c = oracle(state, cell)
if c.verdict == INCONSISTENT: return INCONSISTENT
if c.verdict == UNKNOWN:      return NOT_PROVABLE        # trạng thái game không đổi
if c.verdict.name == status.name:
      lật thẻ: thêm (cell → status) vào proved, thêm clue của cell vào revealed_clues
      return ACCEPTED(revealed_clue=...)
else: return CONTRADICTED                                # trạng thái game không đổi
```

Khi từ chối, engine **không** để lộ clue ẩn và **không** thay đổi trạng thái.

---

## 7. Vòng lặp suy diễn (`orchestration/runner_loop.py`, M5)

```python
def deduction_loop(engine: GameEngine, agent: LogicAgent) -> Iterator[TraceStep]:
    """Generator: mỗi lần yield là một bước (GUI dùng để animate từng lần lật thẻ).
    Kết thúc khi SOLVED / STUCK / INCONSISTENT; trạng thái cuối nằm trong TraceLog."""
```

```
step = 0
while not engine.is_solved():
    state = engine.public_state()
    forced = agent.next_forced(state)
    if forced is None:  terminal = STUCK (hoặc INCONSISTENT); break
    cell, verdict = forced
    result = engine.submit(cell, status_of(verdict))
    step += 1
    yield TraceStep(step, ids(state.revealed_clues), queries, (cell, status), result.revealed_clue.id)
```

`deduction_loop` là **nơi duy nhất** hai bên gặp nhau: gọi agent bằng `PublicState`, gọi engine bằng verdict.

---

## 8. Định dạng puzzle JSON

```json
{
  "n": 3,
  "characters": {
    "A1": {"name": "Abel",  "job": "Astronaut"},
    "B1": {"name": "Bea",   "job": "Cook"}
  },
  "solution": {"A1": "INNOCENT", "B1": "CRIMINAL"},
  "initial_revealed": ["B2"],
  "clues": {
    "A1": {"type": "FACT",      "cell": "C3", "status": "CRIMINAL"},
    "B1": {"type": "SAME",      "a": "A1", "b": "C1"},
    "C1": {"type": "DIFFERENT", "a": "A2", "b": "B2"},
    "A2": {"type": "EXACTLY",   "k": 2, "region": {"kind": "NEIGHBORS", "center": "B2"}},
    "B2": {"type": "AT_LEAST",  "k": 1, "region": {"kind": "ROW", "row": 2}},
    "C2": {"type": "AT_MOST",   "k": 1, "region": {"kind": "COL", "col": "C"}},
    "A3": {"type": "EXACTLY",   "k": 2, "region": {"kind": "CELLS", "cells": ["A1", "B2", "C3"]}},
    "B3": {"type": "PARITY",    "parity": "ODD",
           "region": {"kind": "ROW", "row": 3}},
    "C3": {"type": "COMPARE",   "op": "GT",
           "left":  {"kind": "COL", "col": "A"},
           "right": {"kind": "COL", "col": "B"}}
  }
}
```

Quy ước:

- Ô viết `"C2"` (cột chữ hoa + hàng từ 1). Trong JSON, `ROW` dùng số hàng **1-based**, `COL` dùng **chữ cột**; `loader` chuyển sang chỉ số 0-based nội bộ.
- Khóa của `clues` là ô chứa thẻ đó; `clue.id = "clue@<ô>"`.
- Số `characters`, `solution`, `clues` phải bằng `n²`; thứ tự tên theo bảng chữ cái do puzzle quyết định.
- `loader` raise `PuzzleError` kèm đường dẫn trường lỗi.

Các `type` hợp lệ: `FACT`, `SAME`, `DIFFERENT`, `EXACTLY`, `AT_LEAST`, `AT_MOST`, `PARITY`, `COMPARE`.

---

## 9. GUI (`gui/`, M5)

- GUI chỉ gọi: `engine.submit`, `engine.restart`, `GameEngine.load`, `agent.hint`, `deduction_loop`, và `clue.cells(n)` để highlight.
- **Auto Solve** lặp generator `deduction_loop` bằng `after()` của Tkinter (mỗi bước một nhịp) để thấy từng lần lật thẻ; không khóa luồng giao diện.
- Phân biệt trực quan `NOT_PROVABLE` (màu cảnh báo vàng) và `CONTRADICTED` (màu đỏ).
- Hint hiển thị ô forced và làm sáng clue liên quan; **không** hiển thị đáp án ẩn.

---

## 10. Xử lý lỗi và ngoại lệ

| Ngoại lệ | Khi nào | Ai raise |
|---|---|---|
| `PuzzleError` | JSON sai schema/giá trị | `loader` |
| `ClueError` | tham số clue không hợp lệ (k ngoài `[0, \|R\|]`, ô không tồn tại) | `encoder`, `loader` |
| `SolverTimeout` | DPLL quá `timeout` | `dpll` |
| `InconsistentKB` | KB UNSAT khi cần kết luận | `entailment` (trả `Verdict.INCONSISTENT`, không raise trong luồng chính) |

Terminal states của một lần giải: `SOLVED`, `STUCK` (còn ô chưa giải nhưng không có verdict forced), `INCONSISTENT`, `ERROR`/`TIMEOUT`.

---

## 11. Quy ước code (rút gọn; chi tiết trong `REGULATION.md`)

- Python 3.10+, type hints đầy đủ, docstring ngắn cho hàm công khai.
- Dataclass `frozen=True` cho dữ liệu; không có biến toàn cục thay đổi.
- Không `print` trong `model/` và `logic/`; dùng module `logging`.
- Mọi thứ tự lặp phải xác định: sắp xếp trước khi lặp trên `set`/`dict` khi kết quả ảnh hưởng đến hành vi.
- Đặt tên: `snake_case` (hàm, biến), `PascalCase` (lớp), `UPPER_CASE` (hằng).

---

## 12. Điểm phụ thuộc cần chốt sớm

| Giao ước | Người cung cấp | Người chờ | Hạn |
|---|---|---|---|
| Toàn bộ tài liệu này `FROZEN` | M1 | M2, M3, M4, M5 | cuối nửa đầu Giai đoạn 1 |
| `RegionResolver` + `Clue` + `PublicState` | M2 | M3, M5 | nửa đầu Giai đoạn 1 |
| `DPLLSolver.solve`, `SolverStats`, `SolveResult` | M4 | M3 (test), M5 | nửa đầu Giai đoạn 1 |
| `classify`, `SatQueryRecord`, `next_forced` | M4 | M2, M5 | nửa đầu Giai đoạn 2 |
| `PARITY`, `COMPARE` (clue + schema) | M3 | M2 (puzzle) | nửa đầu Giai đoạn 2; **schema đã khóa ở mục 4.3 và 8** |

Trong lúc chờ: M4 test DPLL bằng CNF viết tay (list số nguyên); M5 dùng engine giả và agent giả (`classify` trả giá trị cố định); M2 kiểm uniqueness tạm bằng brute-force với `semantics.holds`.

---

## 13. Nhật ký thay đổi interface

| Ngày | Thay đổi | Người đề xuất | Duyệt bởi |
|---|---|---|---|
| _điền khi có thay đổi_ | | | |
