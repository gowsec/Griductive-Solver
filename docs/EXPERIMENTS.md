# EXPERIMENTS.md

Thiết kế thực nghiệm đánh giá toàn hệ thống: bộ puzzle, chỉ số, quy trình chạy, các so sánh và cách báo cáo kết quả (kể cả failure và timeout).

- Chủ sở hữu: M5 (chạy, phân tích); M2 hỗ trợ vẽ bảng/biểu đồ; M3, M4 cung cấp phân tích chuyên môn
- Phụ thuộc: [`ARCHITECTURE.md`](ARCHITECTURE.md), [`CNF_MAPPING.md`](CNF_MAPPING.md), [`TEST_CASES.md`](TEST_CASES.md)
- Trạng thái: `DRAFT` (đã đồng bộ với code ngày 22/11/2026; các phần chưa cài đặt được đánh dấu *(kế hoạch)*)

---

## 1. Mục tiêu và câu hỏi nghiên cứu

Đề bài yêu cầu đánh giá hệ thống trên nhiều puzzle 3×3 và 4×4 (5×5 là stress case) và ghi sáu nhóm chỉ số. Ngoài việc ghi số liệu, nhóm đặt các câu hỏi sau để phần *Observations* có nội dung:

| Mã | Câu hỏi | Thí nghiệm |
|---|---|---|
| RQ1 | Chi phí (biến, clause, SAT calls, thống kê DPLL, thời gian) tăng thế nào theo kích thước lưới? | E1 |
| RQ2 | Combinatorial và sequential counter khác nhau ra sao về số biến phụ, số clause và thời gian? Có cho cùng kết luận không? | E2 |
| RQ3 | Chi phí của agent nằm ở đâu: nhiều SAT call hay mỗi call khó? | E1, E3 |
| RQ4 | Clue extension (`PARITY`, `COMPARE`) làm thay đổi chi phí thế nào? | E4 |
| RQ5 | Pure-literal elimination (nếu cài) có giảm thống kê DPLL không? | E5 (tùy chọn) |
| RQ6 | Hệ thống xử lý puzzle lỗi như thế nào (mâu thuẫn, không duy nhất, kẹt)? | E6 |
| RQ7 | Giới hạn mở rộng: lưới 5×5, vùng lớn bắt đầu gây chậm ở đâu? | E1, E7 |

---

## 2. Bộ puzzle

**Một bộ cố định cho mọi so sánh** (nguyên tắc của đề). Đặt tại `puzzles/`, phiên bản hóa bằng Git; không sửa puzzle sau khi bắt đầu chạy kết quả chính thức. Nếu phải sửa, chạy lại toàn bộ.

| Nhóm | File | Số lượng tối thiểu | Vai trò |
|---|---|:-:|---|
| 3×3 | `3x3_*.json` | 3 | Baseline, đối chiếu vét cạn |
| 4×4 | `4x4_*.json` | 3 | Chính |
| 5×5 | `5x5_*.json` | 1 | Stress case |
| Có extension | trong nhóm trên (ít nhất 1 puzzle 3×3 và 1 puzzle 4×4) | | E4 |
| Lỗi | `bad_*.json` | 2 hợp lệ về schema (`bad_not_unique`, `bad_stuck`) dùng cho thực nghiệm; các `bad_*` còn lại bị loader từ chối | E6 |

Quy tắc:
- Mọi puzzle chuẩn phải qua `check_uniqueness` = `UNIQUE` **trước khi** vào bộ.
- Mỗi puzzle ghi trong bảng mô tả ở cuối file này: kích thước, số thẻ lật sẵn, loại clue có mặt, số clue extension.
- `Số clue extension` là tổng số clue `PARITY` và `COMPARE`.
- Puzzle bị loader từ chối (`bad_contradiction`, `bad_solution_mismatch`, `bad_invalid_k`, `bad_missing_cell`, `bad_unknown_cell`, `bad_schema`) thuộc test của loader (`PuzzleError`), không dùng trong thực nghiệm hiệu năng. Khi chạy `experiment` chúng được ghi `status = ERROR` với `size` trống (M5 sẽ ghi `N/A`).

---

## 3. Chỉ số

### 3.1 Định nghĩa

Mỗi lần chạy một puzzle ghi một dòng CSV. Các chỉ số được tổng hợp **trên toàn bộ lần giải** (từ trạng thái đầu đến terminal).

| Cột CSV | Định nghĩa | Nguồn |
|---|---|---|
| `puzzle` | Tên file | runner |
| `size` | N (3, 4, 5) | `Puzzle.n` |
| `encoding` | `combinatorial` hoặc `sequential` | cấu hình |
| `primary_vars` | `N²` | `KB.n_primary` |
| `aux_vars` | Số biến phụ của **KB cuối cùng** (khi đã lộ nhiều clue nhất) | `KB.n_aux` |
| `clauses` | Số clause của **KB cuối cùng** | `KB.n_clauses` |
| `clauses_peak` | Số clause lớn nhất qua các bước (nếu khác `clauses`) | runner |
| `sat_calls` | **Tổng** số lần gọi `DPLLSolver.solve` trong lúc giải (mọi truy vấn của `classify`) | cộng `len(queries)` từ trace |
| `decisions` | Tổng số lần quyết định (phân nhánh) | cộng `SolverStats.decisions` |
| `propagations` | Tổng số lần lan truyền unit | cộng `SolverStats.propagations` |
| `backtracks` | Tổng số lần quay lui | cộng `SolverStats.backtracks` |
| `steps` | Số bước suy diễn (mỗi `ACCEPTED` là một bước) | số `TraceStep` |
| `waves` | Số đợt lật (định nghĩa ở 3.2) | runner |
| `runtime_s` | Thời gian chạy toàn bộ vòng suy diễn (giây, `time.perf_counter`) | runner |
| `unique` | Kết quả `check_uniqueness`: `UNIQUE`, `NOT_UNIQUE`, `UNSAT` | M5 |
| `unique_runtime_s` | Thời gian riêng của `check_uniqueness` | runner |
| `status` | `SOLVED`, `STUCK`, `INCONSISTENT`, `TIMEOUT`, `ERROR` | terminal của trace |
| `error` | Thông điệp lỗi (rỗng nếu không có) | runner |
| `trial` | Số lần lặp (xem mục 4.2) | runner |

> Với `TIMEOUT` hoặc `ERROR`: vẫn ghi các chỉ số đã thu được đến lúc dừng, đánh dấu `status` tương ứng. **Không bỏ dòng.**

`runner.py` ghi đầy đủ các cột mô tả ở mục 3.1. Các cột `decisions`, `propagations`, `backtracks` tổng hợp lượt giải; các cột `unique_*` là thống kê riêng của lượt kiểm duy nhất. `sat_calls` gồm cả truy vấn `next_forced`, truy vấn bên trong `engine.submit`, và hai lần giải uniqueness.

### 3.2 Định nghĩa "đợt lật" (wave)

Suy diễn là **đơn điệu**: một ô đã được suy ra thì vẫn được suy ra khi KB lớn hơn. Vì vậy có thể gom bước theo đợt mà không đổi kết quả cuối:

- Đợt 1: tập mọi ô được suy ra từ KB gồm **chỉ** các clue lật sẵn ban đầu.
- Lật cả đợt 1, thu được clue mới.
- Đợt 2: tập mọi ô mới được suy ra từ KB sau đợt 1, và cứ thế.

`waves` = số đợt cho đến terminal. Ghi `steps` (số lần lật thẻ) và `waves` (độ sâu suy diễn bắc cầu). Với puzzle bị kẹt, `waves` đếm các đợt còn tiến được.

Ý nghĩa: `steps` đo khối lượng công việc, `waves` đo độ sâu chuỗi suy diễn. Hai giá trị tách bạch.

### 3.3 Quy tắc đếm

- `sat_calls` gồm **hai** truy vấn (`KB ∧ ¬C` và `KB ∧ C`) cho mỗi ô được `classify`; không có truy vấn `SAT(KB)` riêng. Tính cả truy vấn của các ô **không** được suy ra (UNKNOWN), vì chúng là chi phí thật.
- Thống kê của `check_uniqueness` **không** cộng vào các cột giải; ghi riêng (`unique_*`).
- Chi phí của engine (hiển thị, lật thẻ) rất nhỏ; vẫn nằm trong `runtime_s` vì đo toàn vòng lặp.
- Số liệu DPLL chỉ so sánh được khi cùng chiến lược chọn biến và cùng cấu hình (pure-literal bật/tắt).

---

## 4. Quy trình chạy

### 4.1 Lệnh

```bash
# Toàn bộ bộ puzzle, cấu hình mặc định (--out là một FILE .csv)
python main.py experiment --suite puzzles/ --timeout 60 --out results/experiment.csv

# Chỉ một nhóm
python main.py experiment --suite puzzles/ --filter 4x4 --out results/4x4.csv

# Giải một puzzle, in từng bước và xuất trace
python main.py solve puzzles/4x4_01.json --trace-csv results/trace_4x4.csv

# (kế hoạch, M5 bổ sung) E2: so sánh mã hóa
python main.py experiment --suite puzzles/ --encoding combinatorial --out results/comb.csv
python main.py experiment --suite puzzles/ --encoding sequential    --out results/seq.csv

# (kế hoạch, M2/M5) Sinh bảng và biểu đồ
python -m griductive.experiments.report_tables --in results/ --out results/figures/
```

### 4.2 Thông số

| Thông số | Giá trị |
|---|---|
| Timeout mỗi puzzle | 60 giây (cho toàn bộ vòng suy diễn). Với `5x5` có thể nâng lên 300 giây, **ghi rõ trong báo cáo** |
| Lặp | 5 lần cho mỗi (puzzle, cấu hình); **chỉ số đếm** (SAT calls, decisions, ...) giống nhau giữa các lần vì chương trình xác định; `runtime_s` báo **trung vị** và khoảng min–max |
| Khởi động | Bỏ lần chạy đầu (làm nóng cache/import), không tính vào kết quả |
| Thứ tự chạy | Cố định (sắp xếp theo tên file) |
| Seed | Không cần (không có ngẫu nhiên). Nếu sau này thêm ngẫu nhiên thì phải ghi seed |

Nếu hai lần chạy cho **chỉ số đếm khác nhau** thì đó là **bug về tính xác định** (nguyên tắc P8), không phải nhiễu thực nghiệm. Báo M1 và M4.

### 4.3 Cấu hình máy

Ghi vào bảng ở mục 9 trước khi chạy: CPU, số nhân, RAM, hệ điều hành, phiên bản Python, tình trạng nguồn điện (laptop cắm sạc), có chạy chương trình nặng song song không. Chạy tất cả số liệu cuối **trên cùng một máy**.

### 4.4 Cách xử lý failure và timeout

| Tình huống | Hành vi runner | Ghi trong báo cáo |
|---|---|---|
| Vượt timeout | Dừng, ghi `status = TIMEOUT` + chỉ số đã thu | Liệt kê trong bảng; phân tích nguyên nhân (vùng lớn? DPLL chậm?) |
| Exception | Bắt, ghi `status = ERROR` + `error`, **tiếp tục** puzzle sau | Liệt kê; sửa lỗi hoặc ghi là hạn chế |
| `STUCK` | Ghi bình thường (là kết quả hợp lệ với puzzle `bad_stuck`/`bad_not_unique`) | Giải thích vì sao không tiến thêm |
| `INCONSISTENT` | Không xuất hiện với puzzle hợp lệ (loader đã chặn); chỉ kiểm bằng unit test | Xem ghi chú dưới bảng E6 |

Nguyên tắc: **không loại bất kỳ puzzle nào khỏi kết quả** vì lỗi hoặc chậm. Nếu bộ puzzle thay đổi giữa chừng thì chạy lại toàn bộ.

---

## 5. Các thí nghiệm

### E1: Chi phí theo kích thước lưới (RQ1, RQ3, RQ7)

- **Dữ liệu:** toàn bộ puzzle chuẩn 3×3, 4×4, 5×5. Cấu hình mặc định (combinatorial).
- **Ghi:** đủ 6 nhóm chỉ số cho từng puzzle.
- **Bảng kết quả:** mỗi dòng một puzzle; thêm dòng trung bình theo nhóm kích thước.
- **Biểu đồ:** cột hoặc đường theo `size` cho `clauses`, `sat_calls`, `decisions`, `runtime_s` (trục log nếu chênh lệch lớn).
- **Quan sát cần trả lời:** chi phí tăng theo `N` thế nào; `sat_calls` xấp xỉ bao nhiêu mỗi bước (kỳ vọng tối đa `2·|unsolved|` mỗi lần tìm ô forced, vì `next_forced` dừng ở ô forced đầu tiên); ai chiếm `runtime` (số lần gọi hay độ khó mỗi lần).

### E2: Combinatorial và sequential counter (RQ2)

- **Dữ liệu:** cùng bộ puzzle, chạy hai lần với `--encoding`.
- **Phải kiểm tra trước:** hai cấu hình cho **cùng verdict ở mọi bước** (xem E2E-06). Nếu không, dừng và sửa encoder.
- **Ghi:** `aux_vars`, `clauses`, `decisions`, `propagations`, `backtracks`, `runtime_s`.
- **Bảng so sánh:** cột theo cặp (combinatorial | sequential) cho mỗi chỉ số; thêm cột tỉ lệ `seq/comb`.
- **Quan sát:** sequential có thêm biến phụ, ít clause hơn trên vùng lớn; trên vùng nhỏ (≤ 8 ô) thường không có lợi. Báo cáo điểm giao nếu quan sát được.

### E3: Phân tích chi phí theo bước (RQ3)

- **Dữ liệu:** một puzzle 4×4 và một 5×5 (đại diện), lấy từ trace.
- **Ghi:** theo từng bước: `clauses` của KB, `sat_calls`, `decisions`, thời gian.
- **Biểu đồ:** đường theo số bước: chi phí mỗi bước tăng hay giảm khi KB lớn hơn (nhiều clue hơn nhưng ít ô chưa giải hơn).
- **Quan sát:** vì ít ô chưa giải hơn, số SAT call mỗi bước giảm dần; KB lớn hơn làm mỗi call đắt hơn, hai xu hướng này đối nhau.

### E4: Ảnh hưởng của clue extension (RQ4)

- **Dữ liệu:** các puzzle có `PARITY`/`COMPARE` so với puzzle cùng cỡ không có.
- **Ghi:** `clauses`, `aux_vars`, `decisions`, `runtime_s`.
- **Lưu ý:** hai puzzle khác nhau về nội dung nên **không so sánh trực tiếp tuyệt đối**; so sánh trên **số clause mỗi clue** (đo riêng bằng cách mã hóa từng clue, không cần chạy solver) để cô lập chi phí mã hóa của extension.
- **Bảng bổ sung:** chi phí mã hóa của từng loại clue: số clause và biến phụ với các kích thước vùng 3, 4, 5, 8 ô.

### E5: Pure-literal elimination (RQ5, chỉ khi M4 cài đặt)

- **Dữ liệu:** cùng bộ puzzle, bật/tắt `pure_literal`.
- **Ghi:** `decisions`, `propagations`, `backtracks`, `runtime_s`.
- **Quan sát:** pure-literal thường ít ảnh hưởng với KB sinh ra từ clue (nhiều literal xuất hiện cả hai dấu); ghi nhận số liệu thực tế thay vì giả định.

### E6: Puzzle lỗi (RQ6)

| Puzzle | Kết quả mong đợi | Kiểm chứng |
|---|---|---|
| `bad_contradiction` | Hai clue `FACT` gán trạng thái đối nghịch cho A1; loader từ chối clue thứ hai | `PuzzleError` tại `$.clues.B1` |
| `bad_not_unique` | `status = STUCK`; `unique = NOT_UNIQUE` | Agent **không đoán**; số bước < số ô chưa giải |
| `bad_stuck` | `status = STUCK`; `unique = UNIQUE` | Khác `bad_not_unique`: puzzle hợp lệ nhưng thiếu thông tin ban đầu |

**Ghi chú về `INCONSISTENT`:** loader xác thực từng clue bằng `solution` và từ chối dữ liệu không nhất quán trước khi chạy puzzle. `bad_contradiction` có hai clue `FACT` đối nghịch (clue thứ hai sai với solution); `bad_solution_mismatch` có một clue sai với solution. Vì vậy không có file puzzle nào cho ra `status = INCONSISTENT`. Trạng thái đó được kiểm chứng bằng **unit test** trên `PublicState` tạo tay (ví dụ `test_agt_08_agent_on_inconsistent_state` trong `tests/test_agent.py`, các test UNSAT trong `tests/test_dpll.py`), không bằng thực nghiệm.

Báo cáo như **kết quả thành công** của hệ thống (hệ thống nhận biết đúng), không phải failure. Phân biệt rõ với failure thật (`TIMEOUT`, `ERROR`) ở mục 6.

### E7: Stress (RQ7)

- **Dữ liệu:** `5x5_*` và, nếu có thể, một puzzle `5x5` cố ý có vùng `CELLS` lớn (ví dụ 13 ô) để buộc chọn cách mã hóa.
- **Ghi:** thời gian, số clause, timeout. Encoder **không tự chuyển** sang sequential; phải chạy riêng hai cấu hình `--encoding` *(kế hoạch)* để so sánh.
- **Quan sát:** nút thắt nằm ở encoder (nổ clause) hay solver; ví dụ đã đo: `Count EQ 12` trên 25 ô, combinatorial sinh khoảng 9,6 triệu clause (~5 giây chỉ để mã hóa).

---

## 6. Báo cáo kết quả

### 6.1 Bảng bắt buộc

**Bảng 1. Kết quả chính theo puzzle** (cấu hình mặc định):

| Puzzle | N | Primary | Aux | Clauses | SAT calls | Decisions | Propagations | Backtracks | Steps | Waves | Runtime (s) | Status |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|---|
| _điền từ CSV_ | | | | | | | | | | | | |

> Cột `Waves` chỉ điền được khi runner bổ sung `waves` *(kế hoạch)*; nếu không kịp thì bỏ cột này và mục 3.2 khỏi báo cáo.

**Bảng 2. Failure, timeout và kết quả bất thường** (không được bỏ trống; ghi "không có" nếu không có):

| Puzzle | Cấu hình | Status | Chỉ số lúc dừng | Nguyên nhân (nếu biết) | Hướng xử lý |
|---|---|---|---|---|---|
| _điền_ | | | | | |

**Bảng 3. So sánh mã hóa** (E2), **Bảng 4. Chi phí mã hóa theo loại clue** (E4), **Bảng 5. Puzzle lỗi** (E6).

### 6.2 Biểu đồ đề xuất

| Hình | Nội dung | Thí nghiệm |
|---|---|---|
| H1 | Clauses, SAT calls, runtime theo kích thước lưới | E1 |
| H2 | So sánh `aux_vars` và `clauses`: combinatorial và sequential | E2 |
| H3 | Chi phí theo bước suy diễn | E3 |
| H4 | Số clause mỗi loại clue theo kích thước vùng | E4 |

Yêu cầu hình: có nhãn trục và đơn vị, chú giải, dùng trục log khi chênh lệch lớn, tên file `results/figures/H<n>_<mô tả>.png`, font đủ lớn để đọc khi chèn vào PDF.

### 6.3 Mục *Observations* và *Limitations*

Mỗi quan sát phải **gắn với số liệu cụ thể** (trích dòng/bảng/hình). Danh sách hạn chế nên có:

- Số lượng puzzle còn ít (không đại diện cho mọi phân bố clue).
- Puzzle do nhóm tự thiết kế (có thể thiên lệch về loại clue nhóm hỗ trợ).
- Runtime phụ thuộc máy và Python (thuật toán thuần Python, không tối ưu như SAT solver chuyên dụng).
- DPLL cơ bản không có học mệnh đề, không dùng heuristic nâng cao; hạn chế trên puzzle lớn hơn 5×5.
- Mã hóa combinatorial có thể bùng nổ với vùng lớn; đã giảm nhẹ bằng sequential counter.
- Số liệu `waves` phụ thuộc vào định nghĩa ở mục 3.2.

---

## 7. Tái lập kết quả

| Việc | Cách làm |
|---|---|
| Mã nguồn | Ghi **commit hash** dùng để chạy trong `results/RUN_INFO.txt` |
| Bộ puzzle | Ghi SHA của thư mục `puzzles/` (hoặc commit hash) |
| Lệnh đã chạy | Lưu nguyên văn trong `results/RUN_INFO.txt` |
| Cấu hình máy | Mục 9 |
| Dữ liệu thô | `results/*.csv` được commit (hoặc đính kèm khi nộp); bảng và hình sinh lại bằng `report_tables.py` |

Ai cũng có thể chạy lại từ đầu bằng các lệnh ở mục 4.1 và thu được **cùng chỉ số đếm**; chỉ `runtime_s` dao động.

---

## 8. Phân công và thời điểm

| Việc | Người | Giai đoạn |
|---|---|---|
| Khung `runner.py` + định dạng CSV | M5 | Giai đoạn 2 |
| Thiết kế bộ puzzle và bảng mô tả | M2 | Giai đoạn 2 |
| Chạy toàn bộ (E1–E7) | M5 | Đầu Giai đoạn 3 |
| `report_tables.py` (bảng, hình) | M2 (hỗ trợ M5) | Giai đoạn 3, sau khi có CSV |
| Phân tích E2 (mã hóa) | M3 | Giai đoạn 3 |
| Phân tích E1/E3/E5 (DPLL, agent) | M4 | Giai đoạn 3 |
| Viết mục Experiments trong báo cáo | M5 | Giai đoạn 3 |

Thực nghiệm chạy trên bản code **đã đóng băng**; nếu sửa lõi (encoder, DPLL, agent) sau khi chạy thì chạy lại toàn bộ.

---

## 9. Phụ lục: điền khi chạy

### 9.1 Cấu hình máy

| Hạng mục | Giá trị |
|---|---|
| CPU | _điền_ |
| Số nhân / luồng | _điền_ |
| RAM | _điền_ |
| Hệ điều hành | _điền_ |
| Python | _điền_ |
| Nguồn điện / chế độ năng lượng | _điền_ |
| Commit hash | _điền_ |

### 9.2 Mô tả bộ puzzle

| File | N | Thẻ lật sẵn | Loại clue có mặt | Số clue extension | `unique` | Ghi chú |
|---|:-:|:-:|---|:-:|:-:|---|
| `3x3_01.json` | 3 | 1 | `AT_LEAST`, `AT_MOST`, `EXACTLY`, `DIFFERENT`, `PARITY`, `COMPARE` | 3 | `UNIQUE` | Giải bằng 8 lần suy diễn; DPLL: 2 decisions, 1 backtrack |
| `4x4_01.json` | 4 | 1 | `AT_LEAST`, `AT_MOST`, `EXACTLY`, `DIFFERENT`, `PARITY`, `COMPARE` | 3 | `UNIQUE` | Giải bằng 15 lần suy diễn; DPLL: 2 decisions, 1 backtrack |
| `5x5_01.json` | 5 | 1 | `AT_LEAST`, `AT_MOST`, `EXACTLY`, `DIFFERENT`, `PARITY`, `COMPARE` | 3 | `UNIQUE` | 24 wave; clue đếm tới 6 ô và parity cả lưới 25 ô; chỉ mở A1 lúc đầu; DPLL: 2 decisions, 1 backtrack |

### 9.3 Checklist trước khi nộp số liệu

- [ ] Mọi puzzle chuẩn đều `UNIQUE`.
- [ ] Chạy đủ 5 lần, bỏ lần khởi động.
- [ ] Hai encoding cho cùng verdict ở mọi bước (E2E-06).
- [ ] Không có puzzle nào bị loại khỏi kết quả; failure và timeout có trong Bảng 2.
- [ ] Mỗi quan sát gắn với số liệu cụ thể.
- [ ] `RUN_INFO.txt` đầy đủ (commit, lệnh, máy).
- [ ] Hình có nhãn trục, đơn vị, chú giải.
