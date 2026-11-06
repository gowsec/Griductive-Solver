# Griductive Solver

> **CSC14003: Introduction to Artificial Intelligence, Project 2**
> Faculty of Information Technology, University of Science, VNU-HCM

Bộ giải **Griductive không đoán mò** (no-guess) bằng Python, dựa trên **logic mệnh đề, mã hóa CNF và thuật toán DPLL tự cài đặt**.

---

## Mục lục

1. [Giới thiệu đồ án](#1-giới-thiệu-đồ-án)
2. [Tính năng](#2-tính-năng)
3. [Yêu cầu hệ thống](#3-yêu-cầu-hệ-thống)
4. [Cấu trúc đồ án](#4-cấu-trúc-đồ-án)
5. [Các tiêu chí chấm điểm](#5-các-tiêu-chí-chấm-điểm)
6. [Cài đặt và chạy chương trình](#6-cài-đặt-và-chạy-chương-trình)
7. [Thành viên và vai trò](#7-thành-viên-và-vai-trò)
8. [Luật chơi tóm tắt](#8-luật-chơi-tóm-tắt)
9. [Hướng dẫn chạy thực nghiệm](#9-hướng-dẫn-chạy-thực-nghiệm)
10. [Tài liệu liên quan](#10-tài-liệu-liên-quan)

---

## 1. Giới thiệu đồ án

Griductive là trò chơi suy luận trên lưới N×N (N ∈ {3, 4, 5}). Mỗi ô là một nhân vật, bí mật là **Criminal** hoặc **Innocent**, và đi kèm một manh mối (clue) **luôn đúng**. Người chơi chỉ được đưa ra kết luận khi nó **suy ra tất yếu** từ thông tin hiện có.

Đồ án xây dựng:

- Một **game** có giao diện đồ họa (Game Engine).
- Một **tác nhân suy diễn** (Logic Agent) tự động tìm các kết luận chắc chắn bằng SAT.
- Toàn bộ pipeline: *clue có cấu trúc → CNF → DPLL → kết luận được suy ra (entailed)*.

Ý tưởng cốt lõi: với mỗi nhân vật `i` chưa giải,

| Điều kiện | Kết luận |
|---|---|
| `KB ∧ ¬Cᵢ` là UNSAT | **CRIMINAL** |
| `KB ∧ Cᵢ` là UNSAT | **INNOCENT** |
| Cả hai đều SAT | **UNKNOWN** (không được đoán) |
| `KB` là UNSAT | **INCONSISTENT** |

---

## 2. Tính năng

**Game và GUI**
- Hiển thị lưới, tọa độ hàng/cột, tên và nghề, thẻ úp/ngửa, trạng thái đã biết.
- Gọi CRIMINAL / INNOCENT cho một nhân vật; thẻ được lật khi kết luận được chứng minh.
- Phân biệt rõ `NOT_PROVABLE` và `CONTRADICTED`; kết luận bị từ chối **không** làm lộ clue ẩn.
- Chọn một clue đã lộ để **highlight** các ô được nhắc tới.
- Các nút **Load / Restart / Hint / Auto Solve**.

**Logic và giải thuật**
- Mã hóa CNF **tự động** cho 6 loại clue bắt buộc: `FACT`, `SAME`, `DIFFERENT`, `EXACTLY`, `AT_LEAST`, `AT_MOST`.
- 2 extension: `PARITY` (chẵn/lẻ) và `COMPARE` (so sánh số lượng giữa hai vùng).
- Hai kiểu mã hóa cardinality: combinatorial và sequential counter.
- **DPLL tự cài đặt**: unit propagation, phát hiện xung đột, branching xác định, backtracking, thống kê decisions / propagations / backtracks / runtime.
- Agent chỉ chọn kết luận được suy ra, sinh **deduction trace**, kiểm tra **tính duy nhất** của lời giải.
- Evaluator ngữ nghĩa trực tiếp cho từng clue, dùng để kiểm chứng encoder.

**Thực nghiệm**
- Chạy cả bộ puzzle 3×3, 4×4, 5×5 với timeout, xuất CSV, bảng và biểu đồ.

---

## 3. Yêu cầu hệ thống

| Hạng mục | Yêu cầu |
|---|---|
| Hệ điều hành | Windows 10+, macOS 12+, hoặc Linux (Ubuntu 20.04+) |
| Python | **3.10 trở lên** |
| GUI | Tkinter (đi kèm Python; trên Ubuntu cài `sudo apt install python3-tk`) |
| Thư viện | Xem `requirements.txt` (tối thiểu: `pytest`; thực nghiệm: `matplotlib`, `pandas`) |
| Cấm | Thư viện SAT có sẵn (`pysat`, `python-sat`, `z3`, ...). DPLL phải tự cài đặt |

---

## 4. Cấu trúc đồ án

```
StudentID1_StudentID2_..._StudentID5/
├── Report.pdf                      # báo cáo (kèm link video demo)
└── Source/
    ├── main.py                     # entry point: gui | cli | experiment
    ├── README.md
    ├── requirements.txt
    ├── docs/
    │   ├── REGULATION.md           # quy ước làm việc nhóm
    │   ├── TASKS.md                # phân công, tiến độ, % đóng góp
    │   ├── ARCHITECTURE.md         # kiến trúc và interface (đã đóng băng)
    │   ├── CNF_MAPPING.md          # ánh xạ clue → CNF
    │   ├── TEST_CASES.md           # kế hoạch kiểm thử
    │   └── EXPERIMENTS.md          # thiết kế thực nghiệm
    ├── puzzles/                    # file JSON: 3x3_*.json, 4x4_*.json, 5x5_*.json, bad_*.json
    ├── griductive/
    │   ├── model/                  # CellId, Status, Region, Clue, Puzzle, PublicState
    │   ├── io/                     # loader.py (JSON → Puzzle, có validate)
    │   ├── engine/                 # game_engine.py
    │   ├── logic/                  # varmap, semantics, cardinality, encoder,
    │   │                           # dpll, entailment, agent, uniqueness, trace
    │   ├── orchestration/          # runner_loop.py (vòng lặp suy diễn dạng generator)
    │   ├── gui/                    # app.py, board_view.py, clue_highlight.py
    │   └── experiments/            # runner.py, report_tables.py
    ├── tests/                      # pytest
    └── results/                    # CSV, bảng, biểu đồ do runner sinh ra

StudentID1_StudentID2/
├── Report.pdf
└── Source/
    ├── main.py                  # entry point: chọn chế độ gui / cli / experiment
    ├── README.md
    ├── requirements.txt
    ├── docs/
    │   ├── REGULATION.md           # quy ước làm việc nhóm
    │   ├── ARCHITECTURE.md         # kiến trúc và interface (đã đóng băng)
    │   ├── CNF_MAPPING.md          # ánh xạ clue → CNF
    │   ├── TEST_CASES.md           # kế hoạch kiểm thử
    │   └── EXPERIMENTS.md          # thiết kế thực nghiệm
    ├── puzzles/                 # file JSON: 3x3_01.json, 4x4_01.json, ...
    ├── griductive/
    │   ├── model/
    │   │   ├── cell.py          # CellId, Character, Status
    │   │   ├── region.py        # Region + RegionResolver
    │   │   ├── clue.py          # Clue dataclasses (6 loại + extension)
    │   │   └── puzzle.py        # Puzzle, PublicState
    │   ├── io/
    │   │   └── loader.py        # parse + validate JSON → Puzzle
    │   ├── engine/
    │   │   └── game_engine.py   # GameEngine, VerdictResult
    │   ├── logic/
    │   │   ├── varmap.py        # VarMap: CellId ↔ biến nguyên
    │   │   ├── semantics.py     # evaluator trực tiếp cho từng clue
    │   │   ├── cardinality.py   # encode ≤k, ≥k, =k
    │   │   ├── encoder.py       # Clue → CNF, build KB_t
    │   │   ├── dpll.py          # DPLLSolver + SolverStats
    │   │   ├── entailment.py    # classify(i) → CRIMINAL/INNOCENT/UNKNOWN
    │   │   ├── uniqueness.py    # đếm tối đa 2 model
    │   │   ├── agent.py         # LogicAgent (deduction loop)
    │   │   └── trace.py         # TraceStep, TraceLog
    │   ├── gui/
    │   │   ├── app.py
    │   │   ├── board_view.py
    │   │   └── clue_highlight.py
    │   └── experiments/
    │       ├── runner.py        # chạy cả bộ puzzle, timeout, ghi CSV
    │       └── report_tables.py # CSV → bảng/biểu đồ cho báo cáo
    └── tests/
        ├── test_semantics_vs_cnf.py
        ├── test_dpll.py
        └── test_agent.py
```

Chi tiết trách nhiệm của từng module: xem [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## 5. Các tiêu chí chấm điểm

| Hạng mục | Điểm | Nội dung chính | Module liên quan |
|---|:---:|---|---|
| Cài đặt lại game | 10 | GUI, lật thẻ, NOT_PROVABLE / CONTRADICTED, highlight clue, Load / Restart / Hint / Auto Solve; tách Game Engine và Logic Agent | `engine/`, `gui/` |
| Mã hóa CNF tự động | 10 | VarMap xác định, validate clue, 6 clue sang CNF, unit clause cho verdict, đếm biến và mệnh đề, evaluator ngữ nghĩa | `logic/varmap, semantics, cardinality, encoder` |
| DPLL SAT solver | 10 | Unit propagation, conflict, branching xác định, backtrack, SAT/UNSAT, thống kê | `logic/dpll` |
| Agent suy diễn | 20 | Phân loại CRIMINAL / INNOCENT / UNKNOWN, không đoán, trace, uniqueness check, Hint không đọc đáp án | `logic/entailment, agent, uniqueness, trace`, `orchestration/` |
| Thực nghiệm | 10 | Nhiều puzzle 3×3 và 4×4 (5×5 là stress case), đủ 6 chỉ số, báo cả failure/timeout | `experiments/` |
| Báo cáo PDF | 30 | Phân công và % đóng góp, formulation, CNF, thuật toán, thực nghiệm, tham khảo, Appendix AI | `Report.pdf` |
| Video demo | 10 | 5 đến 10 phút, có thuyết minh/phụ đề; GUI (5đ) và tính năng (5đ). Link Google Drive, **không dùng YouTube** | Link trong `Report.pdf` |
| **Tổng** | **100** | | |

Ghi chú:
- **Điểm cá nhân = điểm nhóm × % đóng góp** (ghi trong báo cáo và `docs/TASKS.md`).
- Mỗi nhóm phải có **ít nhất 2 extension**.
- Không viết tay CNF cho từng puzzle; không dùng thư viện SAT.
- Giảng viên có thể phỏng vấn ngẫu nhiên: mỗi thành viên phải hiểu code mình nộp.

---

## 6. Cài đặt và chạy chương trình

### 6.1 Cài đặt

```bash
# 1. Lấy mã nguồn
git clone <repo-url>
cd Source

# 2. (Khuyến nghị) tạo môi trường ảo
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Cài thư viện
pip install -r requirements.txt
```

### 6.2 Chạy chương trình

### 6.3 Chạy kiểm thử

---

## 7. Thành viên và vai trò

| Vai trò | Họ tên | Sở hữu|
|---|---|---|
| **M1** Leader, Tích hợp và Báo cáo | Trương Minh Quang | `docs/`, `main.py`, khung `tests/`, báo cáo, video |
| **M2** Mô hình dữ liệu, Engine và Puzzle | _điền sau_ | `model/`, `io/loader.py`, `engine/`, `puzzles/` |
| **M3** Mã hóa CNF | _điền sau_ | `logic/varmap, semantics, cardinality, encoder`, `CNF_MAPPING.md` |
| **M4** SAT và Entailment | _điền sau_ | `logic/dpll, entailment, agent` (classify_all, next_forced, hint) |
| **M5** GUI, Vòng lặp suy diễn và Thực nghiệm | _điền sau_ | `gui/`, `experiments/`, `logic/uniqueness, trace`, `orchestration/` |

Chi tiết task, deadline và trạng thái: [`docs/TASKS.md`](docs/TASKS.md).

---

## 8. Luật chơi tóm tắt

- Lưới N×N; hàng đánh số từ trên xuống (1, 2, ...), cột đánh chữ từ trái sang (A, B, ...). Ví dụ `C2` là cột C, hàng 2.
- Mỗi nhân vật là **Criminal** hoặc **Innocent**. Tên và nghề **không** mang ý nghĩa logic, trừ khi clue nhắc tới.
- Một vài thẻ được lật sẵn lúc đầu; các thẻ còn lại úp.
- **Mọi clue đã lộ đều đúng**, bất kể chủ nhân là ai (không phải bài toán truth-teller/liar).
- Vùng (region) trong clue: **hàng**, **cột**, **hàng xóm** của một ô (8 hướng, không gồm chính ô đó; ô biên có ít hơn), hoặc **danh sách ô tường minh**.
- Sáu loại clue bắt buộc:

| Clue | Ý nghĩa |
|---|---|
| `FACT` | Một người có trạng thái cho trước |
| `SAME` | Hai người cùng trạng thái |
| `DIFFERENT` | Hai người khác trạng thái |
| `EXACTLY(k, R)` | Có đúng k Criminal trong vùng R |
| `AT_LEAST(k, R)` | Có ít nhất k Criminal trong vùng R |
| `AT_MOST(k, R)` | Có nhiều nhất k Criminal trong vùng R |

- **Vòng suy diễn:** chọn một nhân vật chưa giải, gọi CRIMINAL hoặc INNOCENT.
  - Được suy ra từ KB: chấp nhận, lật thẻ, lộ clue mới.
  - Chưa đủ thông tin: `NOT_PROVABLE`.
  - Trạng thái ngược lại mới là điều được suy ra: `CONTRADICTED`.
  - Thẻ không lật và trạng thái game không đổi khi bị từ chối.
- **Không được đoán.** Một puzzle hợp lệ có **đúng một** lời giải.

---

## 9. Hướng dẫn chạy thực nghiệm

### 9.1 Chạy toàn bộ bộ puzzle



### 9.2 Các chỉ số được ghi lại (mỗi puzzle một dòng CSV)

| Cột | Ý nghĩa |
|---|---|
| `puzzle`, `size` | Tên file, kích thước lưới |
| `primary_vars`, `aux_vars` | Số biến chính và biến phụ |
| `clauses` | Số mệnh đề CNF |
| `sat_calls` | Số lần gọi SAT |
| `decisions`, `propagations`, `backtracks` | Thống kê DPLL |
| `steps` (hoặc `waves`) | Số bước suy diễn / đợt lật thẻ |
| `runtime_s` | Thời gian chạy (giây) |
| `status` | `SOLVED`, `STUCK`, `INCONSISTENT`, `NOT_UNIQUE`, `TIMEOUT`, `ERROR` |

### 9.3 Quy tắc thực nghiệm

- Dùng **cùng một bộ puzzle** cho mọi so sánh.
- **Báo cáo đầy đủ failure và timeout**, không loại khỏi kết quả.
- Mỗi puzzle chạy dưới timeout cố định (mặc định 60 giây); nếu đo runtime thì lặp nhiều lần và lấy trung vị.
- Ghi cấu hình máy (CPU, RAM, phiên bản Python) vào `docs/EXPERIMENTS.md`.

Thiết kế chi tiết: [`docs/EXPERIMENTS.md`](docs/EXPERIMENTS.md).

---

## 10. Tài liệu liên quan

| Tài liệu | Nội dung |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Kiến trúc, interface, ranh giới thông tin |
| [`docs/CNF_MAPPING.md`](docs/CNF_MAPPING.md) | Công thức mã hóa từng clue |
| [`docs/TEST_CASES.md`](docs/TEST_CASES.md) | Kế hoạch kiểm thử |
| [`docs/EXPERIMENTS.md`](docs/EXPERIMENTS.md) | Thiết kế thực nghiệm |
| [`docs/REGULATION.md`](docs/REGULATION.md) | Quy ước làm việc nhóm |
| [`docs/TASKS.md`](docs/TASKS.md) | Phân công và tiến độ |

Tham khảo gốc: [Griductive](https://griductive.com) (play page và how-to-play guide, xem đề bài).
