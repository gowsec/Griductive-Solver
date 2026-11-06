# TEST_CASES.md

Kế hoạch kiểm thử của Griductive Solver: nhóm test, các ca cụ thể, bộ puzzle mẫu và tiêu chí pass cho từng hạng mục chấm điểm.

- Chủ sở hữu tài liệu: M1 (khung); mỗi người viết test cho module mình sở hữu
- Công cụ: `pytest` (`pytest tests/ -v`)
- Trạng thái: `DRAFT`

---

## 1. Nguyên tắc

1. **Ai sở hữu module thì viết test cho module đó**, nhưng reviewer chéo phải đọc test.
2. **Test độc lập nhau**: không phụ thuộc thứ tự chạy, không đọc/ghi file ngoài `tests/` và `puzzles/`.
3. **Chuẩn vàng là `semantics.holds`** cho CNF và **brute-force** cho SAT/entailment trên lưới nhỏ. Không so khớp kết quả của một module với chính nó.
4. **Mọi test phải xác định** (không `random` không seed); chạy hai lần cho cùng kết quả.
5. Test bắt lỗi tích cực: có test cho trường hợp **sai** (input không hợp lệ, puzzle hỏng), không chỉ trường hợp đúng.

### 1.1 Quy ước ID

`<NHÓM>-<SỐ>`. Nhóm: `MODEL`, `LOAD`, `ENG`, `CNF`, `DPLL`, `ENT`, `AGT`, `UNQ`, `TRC`, `LOOP`, `ISO`, `GUI`, `E2E`.

Mỗi test trong code có docstring ghi ID (ví dụ `"""CNF-014: EXACTLY(1) trên hàng xóm của A1"""`).

### 1.2 Phân bố theo chủ sở hữu

| Nhóm | Module | Người viết | Reviewer |
|---|---|---|---|
| `MODEL`, `LOAD`, `ENG` | `model/`, `io/`, `engine/` | M2 | M3 |
| `CNF` | `logic/varmap, semantics, cardinality, encoder` | M3 | M4 |
| `DPLL`, `ENT`, `AGT` | `logic/dpll, entailment, agent` | M4 | M2 |
| `UNQ`, `TRC`, `LOOP`, `GUI` | `logic/uniqueness, trace`, `orchestration/`, `gui/` | M5 | M1 |
| `ISO`, `E2E` | toàn hệ thống | M1 | M5 |

---

## 2. Test đơn vị theo module

### 2.1 `MODEL`: mô hình dữ liệu và `RegionResolver` (M2)

| ID | Mô tả | Kỳ vọng |
|---|---|---|
| MODEL-01 | `CellId.parse("C2")` | `CellId(row=1, col=2)`; `str()` trả lại `"C2"` |
| MODEL-02 | `CellId` sắp thứ tự | Sắp xếp cho thứ tự row-major (`A1, B1, C1, A2, ...`) |
| MODEL-03 | `ROW` hàng 1 lưới 3×3 | `A1, B1, C1` |
| MODEL-04 | `COL` cột B lưới 3×3 | `B1, B2, B3` |
| MODEL-05 | `NEIGHBORS` ô giữa `B2` lưới 3×3 | 8 ô, không chứa `B2` |
| MODEL-06 | `NEIGHBORS` góc `A1` | `B1, A2, B2` (3 ô) |
| MODEL-07 | `NEIGHBORS` ô biên `B1` | `A1, C1, A2, B2, C2` (5 ô) |
| MODEL-08 | `NEIGHBORS` lưới 5×5, ô giữa `C3` | 8 ô; ô góc `E5`: 3 ô |
| MODEL-09 | `CELLS` có ô trùng | Báo lỗi |
| MODEL-10 | `CELLS` có ô ngoài lưới | Báo lỗi |
| MODEL-11 | Kết quả của mọi vùng | Sắp xếp row-major, không trùng |
| MODEL-12 | `Clue.cells(n)` | Trả đúng ô được nhắc tới (dùng cho GUI highlight) |

### 2.2 `LOAD`: loader JSON (M2)

| ID | Mô tả | Kỳ vọng |
|---|---|---|
| LOAD-01 | Nạp `3x3_01.json` hợp lệ | `Puzzle` với `n=3`, 9 nhân vật, 9 clue |
| LOAD-02 | Cả 8 `type` clue | Parse đúng thành các lớp `Fact`, `Same`, `Different`, `Count`, `Parity`, `Compare` |
| LOAD-03 | `k < 0` hoặc `k > |R|` | `PuzzleError` kèm đường dẫn trường lỗi |
| LOAD-04 | Thiếu ô (số clue ≠ n²) | `PuzzleError` |
| LOAD-05 | Ô không tồn tại trong clue (`"Z9"`) | `PuzzleError` |
| LOAD-06 | `type` không hợp lệ | `PuzzleError` |
| LOAD-07 | JSON hỏng cú pháp | `PuzzleError` (không crash không rõ lỗi) |
| LOAD-08 | `solution` mâu thuẫn với clue (clue sai trên `solution`) | Cảnh báo/lỗi khi load |
| LOAD-09 | `initial_revealed` chứa ô không tồn tại | `PuzzleError` |
| LOAD-10 | Hàng/cột đổi sang 0-based | `"row": 1` ↔ hàng đầu; `"col": "A"` ↔ cột 0 |

### 2.3 `ENG`: Game Engine (M2)

Dùng **oracle giả** (`lambda state, cell: Classification(...)`) để test độc lập với M4.

| ID | Mô tả | Kỳ vọng |
|---|---|---|
| ENG-01 | `public_state()` lúc đầu | Chỉ có clue/status của `initial_revealed`; `unsolved` sắp xếp row-major |
| ENG-02 | `public_state()` không chứa `solution` hay clue úp | Duyệt toàn bộ trường: không có |
| ENG-03 | Oracle trả `CRIMINAL`, `submit(c, CRIMINAL)` | `ACCEPTED`; `revealed_clue` có giá trị; `proved[c] = CRIMINAL` |
| ENG-04 | Oracle trả `UNKNOWN` | `NOT_PROVABLE`; trạng thái không đổi; `revealed_clue = None` |
| ENG-05 | Oracle trả `CRIMINAL`, `submit(c, INNOCENT)` | `CONTRADICTED`; trạng thái không đổi |
| ENG-06 | Oracle trả `INCONSISTENT` | `INCONSISTENT` |
| ENG-07 | Gọi `submit` lên ô đã giải | Từ chối rõ ràng (không đổi trạng thái) |
| ENG-08 | `restart()` | Về lại đúng `public_state()` ban đầu |
| ENG-09 | Sau khi giải hết | `is_solved() = True` |
| ENG-10 | **Engine không dùng `solution` để quyết định**: đặt `solution` lệch rồi vẫn thấy hành vi theo oracle | Kết quả đổi theo oracle, không theo `solution` |
| ENG-11 | Bị từ chối nhiều lần liên tiếp | Không lộ clue ẩn ở bất kỳ lần nào |

### 2.4 `CNF`: mã hóa (M3)

**Nhóm đối chiếu ngữ nghĩa** (quan trọng nhất). Mỗi ca chạy trên **cả 512 gán** của lưới 3×3 (xem `CNF_MAPPING.md`, mục 7).

| ID | Clue | Vùng | Kỳ vọng |
|---|---|---|---|
| CNF-01 | `FACT CRIMINAL` | một ô | `holds` ≡ CNF |
| CNF-02 | `FACT INNOCENT` | một ô | `holds` ≡ CNF |
| CNF-03 | `SAME` | hai ô | `holds` ≡ CNF |
| CNF-04 | `DIFFERENT` | hai ô | `holds` ≡ CNF |
| CNF-05 | `EXACTLY(k)` k = 0..|R| | hàng, cột, neighbors góc/biên/giữa, `CELLS` | `holds` ≡ CNF với mọi k |
| CNF-06 | `AT_LEAST(k)` k = 0..|R| | như trên | `holds` ≡ CNF |
| CNF-07 | `AT_MOST(k)` k = 0..|R| | như trên | `holds` ≡ CNF |
| CNF-08 | `PARITY` EVEN/ODD | hàng, `CELLS` 1..9 ô | `holds` ≡ CNF |
| CNF-09 | `COMPARE` mọi `op` | hai hàng; hai vùng **giao nhau**; một vùng 1 ô | `holds` ≡ CNF |
| CNF-10 | Sequential counter cho CNF-05..07 | như trên | `holds` ≡ CNF (có biến phụ) |
| CNF-11 | Chuỗi XOR cho `PARITY` ép dùng | `m` lớn | `holds` ≡ CNF |
| CNF-12 | Bộ đếm đơn phân cho `COMPARE` ép dùng | như CNF-09 | `holds` ≡ CNF |

**Nhóm cấu trúc và biên:**

| ID | Mô tả | Kỳ vọng |
|---|---|---|
| CNF-20 | `VarMap`: `A1→1`, `C3→9` (3×3); biến phụ đầu tiên = 10 | Đúng; biến phụ không đụng biến chính |
| CNF-21 | Ví dụ A trong `CNF_MAPPING.md` (`EXACTLY(1)` trên neighbors `A1`) | Đúng 4 clause: `(-2,-4) (-2,-5) (-4,-5) (2,4,5)` (thứ tự clause không quan trọng) |
| CNF-22 | `EXACTLY(2)` trên 4 biến | 8 clause; 6 mô hình thỏa (đếm bằng vét cạn) |
| CNF-23 | `AT_MOST(0)` | `m` unit clause âm |
| CNF-24 | `AT_LEAST(m)` | `m` unit clause dương |
| CNF-25 | `AT_MOST(m)`, `AT_LEAST(0)` | 0 clause |
| CNF-26 | Số clause theo `C(m,k+1)`, `C(m,k-1)` | Khớp bảng ví dụ C (`m = 4`) |
| CNF-27 | `build_kb`: unit clause cho `proved` | `proved[A1]=CRIMINAL` ⇒ có clause `(1)`; `INNOCENT` ⇒ `(-1)` |
| CNF-28 | `build_kb`: không có clue ẩn, không có `solution` | KB chỉ gồm clue của `state.revealed_clues` |
| CNF-29 | `n_primary = N²`; `n_aux`, `n_clauses` khớp thực tế | Thống kê đúng |
| CNF-30 | Cùng input gọi hai lần | Cùng danh sách clause (thứ tự xác định) |
| CNF-31 | Tham số sai (`k > |R|`, `a = b`, vùng rỗng) | `ClueError`, không sinh CNF |
| CNF-32 | Vùng vượt ngưỡng 50 000 | Tự chuyển sequential, có cảnh báo |

### 2.5 `DPLL`: SAT solver (M4)

Chuẩn vàng: vét cạn trên CNF ≤ 12 biến.

| ID | Mô tả | Kỳ vọng |
|---|---|---|
| DPLL-01 | CNF rỗng (0 clause) | SAT; model đầy đủ mọi biến |
| DPLL-02 | Chứa clause rỗng `()` | UNSAT |
| DPLL-03 | `(x1)` | SAT, `x1=True` |
| DPLL-04 | `(x1) ∧ (¬x1)` | UNSAT (phát hiện xung đột bằng propagation, `decisions = 0`) |
| DPLL-05 | Chuỗi unit: `(x1) (¬x1∨x2) (¬x2∨x3)` | SAT, `x1=x2=x3=True`; `decisions = 0` |
| DPLL-06 | **Ví dụ trong đề:** `(A∨B) ∧ (¬A∨B)` | SAT |
| DPLL-07 | Ví dụ trong đề + giả định `¬B` | UNSAT (⇒ `KB ⊨ B`) |
| DPLL-08 | Ví dụ trong đề + giả định `A` và `¬A` riêng lẻ | Cả hai SAT (⇒ `A` là UNKNOWN) |
| DPLL-09 | Pigeonhole 3 bồ câu / 2 chuồng | UNSAT; `backtracks > 0` |
| DPLL-10 | CNF SAT cần phân nhánh | SAT; model **thỏa mọi clause** (kiểm lại bằng đánh giá trực tiếp) |
| DPLL-11 | Assumptions không sửa `clauses` đầu vào | `clauses` giữ nguyên sau khi gọi |
| DPLL-12 | Assumptions mâu thuẫn nhau (`+1`, `-1`) | UNSAT |
| DPLL-13 | Biến không xuất hiện trong clause nào | Có mặt trong model (gán `False` mặc định) |
| DPLL-14 | Thống kê | `decisions`, `propagations`, `backtracks ≥ 0`; `runtime > 0`; SAT thuần propagation ⇒ `decisions = 0` |
| DPLL-15 | Xác định | Chạy hai lần: cùng model, cùng thống kê (trừ `runtime`) |
| DPLL-16 | Ngẫu nhiên có seed cố định: 200 CNF 3-SAT nhỏ (≤ 10 biến) | Kết quả SAT/UNSAT khớp vét cạn trên cả 200 ca |
| DPLL-17 | `timeout` rất nhỏ trên CNF khó | Raise `SolverTimeout` |
| DPLL-18 | Chọn biến | Biến chưa gán nhỏ nhất, thử `True` trước (kiểm bằng cách đọc `decisions` trên CNF dựng sẵn) |

### 2.6 `ENT`: entailment (M4)

Chuẩn vàng: vét cạn mọi mô hình của KB (≤ 16 biến).

| ID | Mô tả | Kỳ vọng |
|---|---|---|
| ENT-01 | KB ví dụ trong đề, `classify(B)` | `CRIMINAL`; 2 truy vấn ghi lại |
| ENT-02 | KB ví dụ trong đề, `classify(A)` | `UNKNOWN` |
| ENT-03 | KB UNSAT (`(A) ∧ (¬A)`) | `INCONSISTENT` cho mọi ô |
| ENT-04 | `INNOCENT`: `KB = (¬A ∨ ¬B) ∧ (A)` ⇒ `classify(B)` | `INNOCENT` |
| ENT-05 | `Classification.queries` | Mỗi bản ghi có `assumption`, `satisfiable`, `stats` |
| ENT-06 | **Bất biến đơn điệu:** thêm clue hợp lệ vào KB | Ô đã `CRIMINAL/INNOCENT` không đổi thành loại khác |
| ENT-07 | Đối chiếu với vét cạn trên 20 KB nhỏ | `classify` khớp "đúng trong mọi mô hình" |
| ENT-08 | Một ô chỉ có 1 mô hình thỏa mà ô khác tự do | Chỉ ô bị buộc mới được phân loại |

### 2.7 `AGT`: agent (M4)

| ID | Mô tả | Kỳ vọng |
|---|---|---|
| AGT-01 | `classify_all` trả đủ mọi ô chưa giải | Không bỏ sót |
| AGT-02 | `next_forced` chọn row-major | Khi nhiều ô forced, trả ô đầu tiên theo row-major |
| AGT-03 | `next_forced` khi không có ô forced | `None` |
| AGT-04 | **Không đoán:** trên 10 trạng thái, mọi verdict mà `next_forced` đưa ra phải đúng trong **mọi** mô hình (vét cạn) | 100% đúng |
| AGT-05 | `hint` trả ô forced + clue đã lộ có chứa ô đó | `related_clue_ids` đều thuộc `state.revealed_clues` |
| AGT-06 | `hint` khi kẹt | Báo không có hint (không bịa) |
| AGT-07 | **Hint/agent không phụ thuộc `solution`:** chạy lại với `Puzzle.solution` bị đảo | Kết quả agent **giống hệt** |
| AGT-08 | Agent trên trạng thái mâu thuẫn | Phát hiện `INCONSISTENT`, không trả verdict |
| AGT-09 | `classify` dùng làm oracle cho engine | Khớp `Oracle` signature |

### 2.8 `UNQ`: tính duy nhất (M5)

| ID | Mô tả | Kỳ vọng |
|---|---|---|
| UNQ-01 | Puzzle hợp lệ (1 lời giải) | `UNIQUE`, `models_found = 1` |
| UNQ-02 | Puzzle có ≥ 2 lời giải | `NOT_UNIQUE`, `models_found = 2`, hai model khác nhau trên biến chính |
| UNQ-03 | Puzzle vô nghiệm | `UNSAT`, `models_found = 0` |
| UNQ-04 | Model tìm được thỏa `semantics.holds` cho mọi clue | Đúng |
| UNQ-05 | Blocking clause chỉ trên biến chính | Biến phụ không làm "nhân đôi" model (kiểm bằng sequential counter) |
| UNQ-06 | Lời giải tìm được khớp `solution` trong file (với puzzle `UNIQUE`) | Khớp |
| UNQ-07 | Đối chiếu vét cạn 2⁹ trên 5 puzzle 3×3 | Số model khớp |

### 2.9 `TRC` và `LOOP`: trace và vòng lặp (M5)

| ID | Mô tả | Kỳ vọng |
|---|---|---|
| TRC-01 | `TraceStep` đủ trường | `step` bắt đầu từ 1; có `active_clue_ids`, `sat_queries`, `verdict`, `revealed_clue_id` |
| TRC-02 | `to_json()` | JSON hợp lệ; đọc lại không mất thông tin |
| TRC-03 | `to_csv()` | Một dòng mỗi bước; header đúng |
| LOOP-01 | Giải hết puzzle hợp lệ 3×3 | Terminal `SOLVED`; số bước = số ô chưa lật lúc đầu |
| LOOP-02 | Puzzle bị kẹt (`bad_stuck`) | Terminal `STUCK`, không đoán thêm ô nào |
| LOOP-03 | Puzzle mâu thuẫn | Terminal `INCONSISTENT` |
| LOOP-04 | Mỗi bước, engine trả `ACCEPTED` | Không có `NOT_PROVABLE`/`CONTRADICTED` trong luồng tự động |
| LOOP-05 | Là generator | Mỗi lần `next()` làm đúng một bước; có thể dừng giữa chừng |
| LOOP-06 | Xác định | Hai lần chạy: trace giống hệt (trừ `runtime`) |
| LOOP-07 | Số bước/đợt (waves) | Khớp định nghĩa trong `EXPERIMENTS.md` |

### 2.10 `GUI`: kiểm tra thủ công (M5) + smoke test

Smoke test tự động: khởi tạo cửa sổ, nạp puzzle, đóng, không lỗi (bỏ qua nếu môi trường không có màn hình).

Checklist thủ công (chạy trước khi quay video):

| ID | Hành động | Kỳ vọng |
|---|---|---|
| GUI-01 | Mở `python main.py gui`, Load puzzle 3×3 | Hiển thị lưới, tọa độ hàng/cột, tên, nghề, thẻ úp/ngửa |
| GUI-02 | Chọn một clue đã lộ | Highlight đúng các ô được nhắc/đếm (`clue.cells(n)`) |
| GUI-03 | Gọi verdict **được suy ra** đúng | Thẻ lật, hiển thị trạng thái, lộ clue mới |
| GUI-04 | Gọi verdict khi chưa đủ thông tin | Báo `NOT_PROVABLE` (màu khác `CONTRADICTED`), thẻ không lật, clue không lộ |
| GUI-05 | Gọi verdict ngược với điều được suy ra | Báo `CONTRADICTED`, thẻ không lật |
| GUI-06 | Hint | Chỉ ra ô có thể chứng minh + clue liên quan; **không** lật thẻ |
| GUI-07 | Auto Solve | Lật từng thẻ có nhịp, dừng khi xong hoặc kẹt, không treo cửa sổ |
| GUI-08 | Restart | Về trạng thái ban đầu |
| GUI-09 | Load puzzle 4×4 và 5×5 | Lưới vẽ đúng, không tràn |
| GUI-10 | Load file hỏng | Thông báo lỗi rõ ràng, không crash |

---

## 3. Test kiến trúc và tích hợp

### 3.1 `ISO`: ranh giới thông tin (M1)

| ID | Mô tả | Kỳ vọng |
|---|---|---|
| ISO-01 | Quét import trong `griductive/logic/`: không có `griductive.engine`, không có `griductive.orchestration`, `griductive.gui` | Không vi phạm (CI fail nếu vi phạm) |
| ISO-02 | Quét import trong `griductive/engine/`: không có `griductive.logic` | Không vi phạm |
| ISO-03 | Quét `griductive/logic/` không đọc thuộc tính `.solution` hay `.clues` của `Puzzle` | Không vi phạm |
| ISO-04 | Quét `requirements.txt` và import: không có `pysat`, `z3`, `pycosat`, `pycryptosat`, `ortools` | Không vi phạm |
| ISO-05 | Quét `puzzles/` và `tests/`: không có CNF viết tay theo puzzle (không có file `.cnf`, không có literal clause cố định gắn tên puzzle ngoài test đơn vị) | Không vi phạm |
| ISO-06 | `PublicState` không chứa tham chiếu tới `Puzzle` | Duyệt thuộc tính: không có |
| ISO-07 | Hai lần chạy cùng puzzle: trace giống nhau (tính xác định, P8) | Giống |

### 3.2 `E2E`: đầu-cuối (M1)

| ID | Mô tả | Kỳ vọng |
|---|---|---|
| E2E-01 | CLI: `3x3_01.json` | `SOLVED`; in số biến/mệnh đề, thống kê DPLL |
| E2E-02 | CLI: mọi `3x3_*`, `4x4_*` | `SOLVED` |
| E2E-03 | `--check-unique` trên toàn bộ puzzle chuẩn | `UNIQUE` |
| E2E-04 | `experiment` trên bộ puzzle | Xuất CSV, không crash; failure và timeout có dòng riêng |
| E2E-05 | Chạy từ máy sạch theo `README.md` | Cài đặt và chạy được |
| E2E-06 | `--encoding sequential` trên bộ puzzle | Cùng verdict và cùng trace (khác số biến/clause/thống kê) |

> **Bất biến E2E-06:** hai kiểu mã hóa phải cho **cùng kết luận** ở mọi bước. Nếu khác, có bug trong encoder.

---

## 4. Bộ puzzle mẫu

Nội dung từng puzzle do M2 thiết kế; **kỳ vọng** dưới đây là hợp đồng mà mỗi puzzle phải thỏa. Mọi puzzle "chuẩn" phải qua `check_uniqueness` (UNQ) trước khi vào bộ.

### 4.1 Puzzle chuẩn (phải `SOLVED`)

| File | Cỡ | Yêu cầu nội dung | Kỳ vọng |
|---|:-:|---|---|
| `3x3_01.json` | 3×3 | Chỉ 6 clue cơ bản, ít thẻ lật sẵn | `UNIQUE`, `SOLVED` |
| `3x3_02.json` | 3×3 | Có clue đếm với `neighbors` | `UNIQUE`, `SOLVED` |
| `3x3_03.json` | 3×3 | Có ít nhất 1 clue extension (`PARITY` hoặc `COMPARE`) | `UNIQUE`, `SOLVED` |
| `4x4_01.json` | 4×4 | Cơ bản + `CELLS` | `UNIQUE`, `SOLVED` |
| `4x4_02.json` | 4×4 | Cần nhiều "đợt" lật (suy diễn bắc cầu) | `UNIQUE`, `SOLVED` |
| `4x4_03.json` | 4×4 | Có cả `PARITY` và `COMPARE` | `UNIQUE`, `SOLVED` |
| `5x5_01.json` | 5×5 | Stress: nhiều clue vùng lớn (hàng/cột 5 ô) | `UNIQUE`, `SOLVED` (có thể chậm; ghi nhận thời gian) |

### 4.2 Puzzle cố ý lỗi (phải bị phát hiện đúng)

| File | Lỗi | Kỳ vọng |
|---|---|---|
| `bad_contradiction.json` | Hai clue mâu thuẫn trực tiếp (ví dụ `FACT A1 CRIMINAL` và `FACT A1 INNOCENT` cùng lộ) | `check_uniqueness`: `UNSAT`; agent: `INCONSISTENT` |
| `bad_not_unique.json` | Thiếu clue, có ≥ 2 lời giải đầy đủ | `check_uniqueness`: `NOT_UNIQUE`; agent kết thúc `STUCK` (không đoán) |
| `bad_stuck.json` | Hợp lệ (duy nhất) nhưng suy diễn từ trạng thái đầu không tiến được | Agent: `STUCK`; không lật thẻ nào ngoài thẻ ban đầu |
| `bad_invalid_k.json` | `EXACTLY` với `k > |R|` | Loader: `PuzzleError` |
| `bad_missing_cell.json` | Thiếu clue của một ô | Loader: `PuzzleError` |
| `bad_unknown_cell.json` | Clue nhắc ô `"Z9"` | Loader: `PuzzleError` |
| `bad_schema.json` | `type` không tồn tại / thiếu trường | Loader: `PuzzleError` |
| `bad_solution_mismatch.json` | `solution` không thỏa một clue | Loader: lỗi hoặc cảnh báo rõ |

> Cần phân biệt: `bad_not_unique` và `bad_stuck` đều dẫn đến `STUCK`, nhưng uniqueness check cho kết quả khác nhau (`NOT_UNIQUE` và `UNIQUE`). Cả hai đều phải có test riêng.

### 4.3 Puzzle nhỏ cho test đối chiếu vét cạn

Bộ puzzle 3×3 tối thiểu (≤ 5 clue) viết tay trong code test (không cần file), để đối chiếu `classify`/`UNQ` với vét cạn 2⁹.

---

## 5. Tiêu chí pass theo hạng mục chấm điểm

| Hạng mục (điểm) | Điều kiện đạt (checklist) | Test liên quan |
|---|---|---|
| **Game (10)** | GUI đủ chức năng ở mục 2.10; phân biệt `NOT_PROVABLE` / `CONTRADICTED`; từ chối không lộ clue; Engine và Agent tách biệt | GUI-*, ENG-*, ISO-* |
| **CNF (10)** | Mapping xác định; mọi clue cơ bản + 2 extension đối chiếu `semantics = CNF` trên 512 gán; unit clause cho verdict; KB không chứa thông tin ẩn; báo cáo số biến/clause | CNF-01..32 |
| **DPLL (10)** | Có unit propagation, phát hiện xung đột, branching xác định, backtrack; SAT trả model đầy đủ; ghi decisions/propagations/backtracks/runtime; khớp vét cạn | DPLL-01..18 |
| **Agent (20)** | Phân loại đúng; **không đoán** (AGT-04); trace đủ trường; uniqueness check riêng; hint không đọc `solution`; xử lý `STUCK` và `INCONSISTENT` | ENT-*, AGT-*, UNQ-*, TRC-*, LOOP-* |
| **Thực nghiệm (10)** | Chạy đủ bộ puzzle 3×3, 4×4 (+5×5); đủ 6 chỉ số; failure/timeout được ghi | E2E-04, `EXPERIMENTS.md` |
| **Báo cáo / Video** | Không có test tự động; xem checklist trong `TASKS.md` | |

---

## 6. Chạy test và CI

```bash
pytest tests/ -v                          # tất cả
pytest tests/ -k "CNF"                    # theo nhóm
pytest tests/ -k "semantics" -x           # dừng ở lỗi đầu tiên
```

- CI (do M1 dựng) chạy `pytest` trên mỗi PR; **không merge nếu fail**.
- Test chậm (ví dụ DPLL-16, `5x5_01`) đánh dấu `@pytest.mark.slow`, chạy trong CI nhưng có thể bỏ qua cục bộ bằng `-m "not slow"`.
- Mục tiêu coverage tham khảo: `logic/` ≥ 85%, `model/`, `io/`, `engine/` ≥ 80%.

---

## 7. Quy trình xử lý khi test fail

1. Người sở hữu module chịu trách nhiệm sửa, trừ khi lỗi nằm ở test.
2. Nếu lỗi nằm ở **interface** (hai module hiểu khác nhau), báo M1 và ghi vào mục 13 của `ARCHITECTURE.md`.
3. Không "sửa" test cho khớp code khi chưa chứng minh được kỳ vọng sai. Với CNF và SAT, chuẩn vàng là `semantics.holds` và vét cạn.
4. Lỗi tìm thấy sau khi nộp bản nháp báo cáo: ghi vào `TASKS.md`, cập nhật số liệu liên quan trong `EXPERIMENTS.md`.
