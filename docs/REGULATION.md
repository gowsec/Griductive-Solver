# REGULATION.md

Quy ước làm việc chung của nhóm.
- Chủ sở hữu tài liệu: Quang
- Liên quan: [`ARCHITECTURE.md`](ARCHITECTURE.md), [`TASKS.md`](TASKS.md), [`TEST_CASES.md`](TEST_CASES.md)
- Trạng thái: `FROZEN`

---

## 1. Tóm tắt 10 điều cần nhớ

1. **Không commit trực tiếp lên `main` & `dev`.** Mọi thay đổi đi qua nhánh và Pull Request (PR).
2. **Mỗi PR phải tag đúng Reviewer** được phân công.
3. Reviewer phản hồi trong **12 giờ**. Chỉ merge khi có trạng thái **Approve**.
5. Code mới phải đi kèm **unit test** trong `tests/`.
7. Mọi hàm và tham số có **type hints**; lớp và hàm công khai có **docstring**.
8. **Agent không import Engine, không đọc đáp án ẩn; không dùng thư viện SAT có sẵn; không viết tay CNF theo puzzle.**
9. **Gặp blocker hoặc trễ tiến độ thì báo ngay**, không tự giữ quá nửa ngày.
10. **Ghi lại việc dùng AI** (prompt quan trọng) ngay lúc dùng, và **hiểu code mình nộp**: có thể bị phỏng vấn.
11. Trong Git Board đã phân nhiệm vụ của mỗi người thành 2 giai đoạn riêng (phần A + phần B) và review, nhằm đảm bảo mọi người đều có thể chạy file ổn định không thiết sót dữ liệu. 
> **Lưu ý:** luôn check kỹ deadline của cá nhân để tránh việc để người khác đợi nếu không hiệu ứng domino sẽ khiến công việc giảm hiệu suất và không theo đúng tiến độ và có thể dẫn đến trễ deadline
---

## 2. Quản lý nhánh (Branching)

### 2.1 Nhánh chính

| Nhánh | Vai trò | Ai được ghi |
|---|---|---|
| `main` | Luôn chạy được. Nguồn của bài nộp | **Không ai commit trực tiếp.** Chỉ cập nhật qua merge PR |
| `dev` | Bản trong quá trình thực thi và được merge vào nhánh main sau khi chốt sản phẩm | **Không ai commit trực tiếp.** Chỉ cập nhật qua merge PR |

M1 bật bảo vệ nhánh `main` & `dev` trên nền tảng Git (bắt buộc PR, bắt buộc CI xanh, bắt buộc ít nhất 1 Approve, cấm force-push).

### 2.2 Nhánh làm việc

**Quy tắc Git & Review Code**

Nhóm sử dụng mô hình "Nhánh cá nhân".

1. **Nhánh cá nhân:** Mỗi người chỉ dùng ĐÚNG 1 nhánh duy nhất trong suốt dự án: `feat/m1`, `feat/m2`, `feat/m3`, `feat/m4`, `feat/m5`.
2. **Quy trình nộp code (Pull Request):**
   - Làm xong -> push code lên nhánh cá nhân (`feat/m*`).
   - Lên GitHub/GitLab mở Pull Request (PR) ghép vào `dev`.
   - **Đặt tên PR cho rõ ràng** (Ví dụ: `[M2] Xong phần RegionResolver`) để người review biết bên trong có gì.
3. **Quy tắc Review (SLA 12h):**
   - Tag đúng người review chéo. Người review có 12 tiếng để vào đọc, test thử và bấm Approve.
   - Khi PR được merge, **KHÔNG xóa nhánh**.
4. **LƯU Ý (Tránh Conflict):**
   - **Bắt buộc:** Trước khi code tính năng tiếp theo, bạn phải kéo code mới nhất từ dev về nhánh của mình: `git fetch origin`, `git pull origin dev` (hoặc `git merge main` trên nhánh của bạn) để đồng bộ.

---

## 3. Quy ước commit

Dùng **Conventional Commits**:

```
<loại>: <mô tả ngắn, mệnh lệnh>

[thân commit tùy chọn: giải thích vì sao, không chỉ là gì]
```

| Loại | Ý nghĩa | Ví dụ |
|---|---|---|
| `feat` | Thêm chức năng | `feat: thêm hàm RegionResolver` |
| `fix` | Sửa lỗi | `fix: lỗi vòng lặp vô hạn ở Agent` |
| `docs` | Tài liệu | `docs: cập nhật CNF_MAPPING mục sequential counter` |
| `test` | Test | `test: thêm test semantics = CNF cho EXACTLY` |
| `refactor` | Không đổi hành vi | `refactor: tách cardinality khỏi encoder` |
| `chore` | Cấu hình | `chore: fix something` |

Quy tắc:
- Một commit làm một việc; mô tả ngắn gọn.
- Không commit: file tạm, cache (`__pycache__`, `.venv`), file hệ điều hành, kết quả chạy lớn, thông tin cá nhân. Giữ `.gitignore` cập nhật.

---

## 4. Pull Request và Review chéo

### 4.1 Người tạo PR (Author)

1. Tạo PR từ nhánh làm việc vào `main`, đặt tiêu đề theo Conventional Commits.
2. **Gán Reviewer đúng theo bảng phân công** (mục 4.3) và **tag Reviewer trong PR** (`@tên`).
4. Điền mẫu mô tả PR (mục 4.2); tự kiểm tra checklist trước khi nhờ review.
5. Sửa theo phản hồi, trả lời từng góp ý; không tự merge khi chưa có Approve.

> **Quy tắc tag:** ai xong và tạo PR thì **phải tag Reviewer** để họ biết vào kiểm tra. PR không có tag coi như chưa gửi.

### 4.2 Mẫu mô tả PR

```markdown
## Mô tả
<Làm gì, vì sao>

## Cách kiểm tra
<Lệnh chạy test, ví dụ: pytest tests/test_dpll.py -v>

## Checklist
- [ ] Có unit test cho phần mới
- [ ] Có type hints và docstring cho hàm/lớp công khai
- [ ] Không vi phạm quy tắc kiến trúc (mục 8)
- [ ] Có cập nhật tài liệu liên quan (nếu đổi interface)
```

### 4.3 Reviewer theo phân công

| Người viết | Reviewer |
|---|---|
| M2 | M3 |
| M3 | M4 |
| M4 | M2 |
| M5 | M1 |
| M1 | M5 |

PR đụng vào code của người khác (ngoài phần mình sở hữu) thì **thêm chủ sở hữu file đó vào làm Reviewer**.


### 4.5 Checklist review

- [ ] Đúng chức năng và đúng đặc tả trong `docs/`
- [ ] Không phá quy tắc kiến trúc (mục 8)
- [ ] Có test đi kèm, test có ý nghĩa (có cả ca sai/biên)
- [ ] Type hints, docstring, comment ở đoạn thuật toán khó
- [ ] Không có code chết, `print` gỡ lỗi, thông tin nhạy cảm
- [ ] Thứ tự duyệt xác định (không phụ thuộc thứ tự `set`/`dict` khi ảnh hưởng kết quả)

### 4.6 Quy tắc merge

| Điều kiện | Bắt buộc |
|---|---|
| Có ít nhất 1 Approve từ Reviewer được phân công | Có |
| Không còn thảo luận chưa giải quyết | Có |
| Cập nhật theo `dev` mới nhất (không xung đột) | Có |

Ngoại lệ **hotfix** (lỗi nghiêm trọng chặn cả nhóm, hoặc sau code freeze): M1 có thể chỉ định review nhanh; vẫn phải qua PR và CI.

---

## 5. Quy chuẩn code Python

- **Python 3.10 trở lên.**
- Đặt tên: `snake_case` (hàm, biến, module), `PascalCase` (lớp), `UPPER_CASE` (hằng số). Tên có nghĩa, tránh viết tắt khó hiểu.
- Dữ liệu dùng `@dataclass(frozen=True)` khi có thể; không dùng biến toàn cục thay đổi.
- Không `print` trong `model/` và `logic/`; dùng `logging`. Chỉ CLI/GUI mới in ra màn hình.
- Không bắt `except:` trống; bắt đúng loại ngoại lệ (`PuzzleError`, `ClueError`, `SolverTimeout`, ...).
- Không dùng `random` không có seed; mọi kết quả phải **xác định** (cùng đầu vào cho cùng đầu ra).

---

## 6. Tài liệu hóa mã nguồn

- Mọi **lớp** và **hàm công khai** có docstring ngắn gọn: làm gì, tham số, giá trị trả về, ngoại lệ có thể xảy ra.
- **Comment rõ ràng tại các đoạn thuật toán phức tạp**: DPLL (unit propagation, backtracking), mã hóa CNF (vì sao lấy `m−k+1`, sequential counter), `RegionResolver`, uniqueness. Comment giải thích **vì sao**, không lặp lại **cái gì**.
- Khi đổi interface hoặc hành vi, cập nhật tài liệu `docs/` trong cùng PR.
- `README.md` luôn đúng với cách cài đặt và chạy thực tế (M1 kiểm tra trước khi nộp trên máy sạch).


---

## 7. Phạm vi sở hữu file

- Mỗi người **chỉ sửa trực tiếp file mình sở hữu** (bảng ở `ARCHITECTURE.md` mục 3 và `README.md` mục 7).
- Cần sửa file của người khác: **báo họ**, hoặc tạo PR và **tag chủ sở hữu** làm Reviewer.
- File dùng chung (`main.py`, `docs/`, CI) do M1 quản lý; đề xuất qua PR.
---

## 8. Dùng AI và liêm chính học thuật

Đề cho phép dùng AI nhưng yêu cầu dùng có trách nhiệm và có thể phỏng vấn ngẫu nhiên.

- Ghi lại việc dùng AI ngay khi dùng: công cụ, prompt quan trọng, kết quả dùng được hay không, người dùng.
- Không dán code AI vào mà không hiểu. Mỗi người phải giải thích được từng dòng quan trọng của phần mình sở hữu (DPLL, mã hóa CNF, agent, ...).
- Mọi code do AI sinh phải được kiểm thử như code thường; không tin kết quả mà chưa có test.
- Không sao chép code từ nhóm khác, repo ngoài mà không ghi nguồn. Mã tham khảo phải ghi trong phần References của báo cáo.
- Không dùng thư viện SAT có sẵn.

