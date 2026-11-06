# CNF_MAPPING.md

Ánh xạ từ **clue có cấu trúc** sang **CNF**. Đây là đặc tả cho `logic/encoder.py`, `cardinality.py` và là nguyên liệu trực tiếp cho mục *CNF encoding* của báo cáo.

- Chủ sở hữu: M3
- Phụ thuộc: [`ARCHITECTURE.md`](ARCHITECTURE.md) (mục 4 và 5)
- Trạng thái: `DRAFT`

---

## 1. Quy ước chung

### 1.1 Biến và literal

| Ký hiệu | Ý nghĩa |
|---|---|
| `Cᵢ` | Nhân vật `i` là Criminal (`True`) hoặc Innocent (`False`) |
| `var(i) = r·N + c + 1` | Chỉ số biến chính của ô `(r, c)`, 0-based, từ `1` đến `N²` |
| Biến phụ | Từ `N² + 1` trở lên, cấp bằng `VarMap.new_aux()` |
| Literal | `+v` là `v` đúng, `-v` là `¬v` (kiểu DIMACS) |
| Clause | `tuple[int, ...]` (phép **hoặc** các literal) |
| CNF | `list[Clause]` (phép **và** các clause) |

Ví dụ lưới 3×3: `A1=1, B1=2, C1=3, A2=4, B2=5, C2=6, A3=7, B3=8, C3=9`.

### 1.2 Bất biến của mọi phép mã hóa

| # | Bất biến | Ý nghĩa |
|---|---|---|
| I1 | **Tương đương theo mô hình chính** | Với mọi gán đầy đủ `a` cho biến chính: `holds(clue, a) = True` ⟺ tồn tại gán biến phụ để CNF thỏa mãn |
| I2 | **Biến phụ được xác định bởi biến chính** | Với mỗi gán biến chính thỏa clue, gán biến phụ thỏa CNF là **duy nhất** (cần cho đếm model/uniqueness không bị nhân đôi; xem mục 6) |
| I3 | **Không dùng biến phụ trong `Cᵢ` ↔ ô** | Biến phụ không ánh xạ ra ô nào |
| I4 | **Xác định** | Cùng clue, cùng `VarMap` cho cùng danh sách clause (sắp xếp theo thứ tự cố định) |

> **Lưu ý về I2:** vì uniqueness check chặn model chỉ trên biến chính nên I2 không bắt buộc cho tính đúng đắn, nhưng nên giữ để số liệu `aux_vars` và thời gian có ý nghĩa so sánh. Sequential counter dạng **tương đương hai chiều** (mục 4.3) thỏa I2; dạng một chiều thì không, nhưng vẫn đúng theo I1.

### 1.3 Kiểm tra tham số (trước khi mã hóa)

Vi phạm → raise `ClueError` (không sinh CNF).

| Điều kiện | Áp dụng cho |
|---|---|
| Ô được nhắc tới nằm trong lưới | mọi clue |
| Vùng không rỗng; ô trong `CELLS` đôi một khác nhau | clue có vùng |
| `0 ≤ k ≤ \|R\|` | `Count` |
| `a ≠ b` | `Same`, `Different` |
| `parity ∈ {EVEN, ODD}` | `Parity` |
| `op ∈ {LT, LE, EQ, GE, GT}`, hai vùng không rỗng | `Compare` |

Vùng được giải ra ô bằng `RegionResolver.cells(region, n)` (**duy nhất**, nguyên tắc P5).

### 1.4 Xây dựng KB tại bước t

```
KB_t = ⋀ encode(clue)  với clue ∈ state.revealed_clues
     ∧ ⋀ unit(Cᵢ)       với (i → CRIMINAL)  ∈ state.proved     # clause (+var(i))
     ∧ ⋀ unit(¬Cᵢ)      với (i → INNOCENT) ∈ state.proved     # clause (-var(i))
```

Thống kê báo cáo: `n_primary = N²`, `n_aux` = số biến phụ đã cấp cho KB, `n_clauses = len(clauses)`.

Quy tắc dọn dẹp (tùy chọn, không đổi ngữ nghĩa): bỏ clause trùng, bỏ clause chứa cặp `v` và `¬v` (tautology).

---

## 2. Bảng tổng hợp

| Clue | Công thức logic | Mã hóa CNF | Số clause | Biến phụ |
|---|---|---|---|---|
| `FACT(i, CRIMINAL)` | `Cᵢ` | `(+i)` | 1 | 0 |
| `FACT(i, INNOCENT)` | `¬Cᵢ` | `(-i)` | 1 | 0 |
| `SAME(i, j)` | `Cᵢ ↔ Cⱼ` | `(-i ∨ +j) ∧ (+i ∨ -j)` | 2 | 0 |
| `DIFFERENT(i, j)` | `Cᵢ ⊕ Cⱼ` | `(+i ∨ +j) ∧ (-i ∨ -j)` | 2 | 0 |
| `EXACTLY(k, R)` | `Σ = k` | `AtMost(k) ∧ AtLeast(k)` | xem mục 4 | 0 hoặc có |
| `AT_LEAST(k, R)` | `Σ ≥ k` | `AtLeast(k)` | xem mục 4 | 0 hoặc có |
| `AT_MOST(k, R)` | `Σ ≤ k` | `AtMost(k)` | xem mục 4 | 0 hoặc có |
| `PARITY(R, p)` *(ext)* | `Σ ≡ p (mod 2)` | mục 5 | `2^(m-1)` hoặc dạng chuỗi XOR | 0 hoặc `m-1` |
| `COMPARE(L, op, R)` *(ext)* | `Σ_L op Σ_R` | mục 6 | tùy cách | 0 hoặc có |

---

## 3. Clue nhị phân và FACT

### 3.1 FACT

```
FACT(i, CRIMINAL)  →  [(+var(i))]
FACT(i, INNOCENT)  →  [(-var(i))]
```

### 3.2 SAME: `Cᵢ ↔ Cⱼ`

Dẫn xuất (dùng cho báo cáo):

```
Cᵢ ↔ Cⱼ
≡ (Cᵢ → Cⱼ) ∧ (Cⱼ → Cᵢ)
≡ (¬Cᵢ ∨ Cⱼ) ∧ (¬Cⱼ ∨ Cᵢ)
```

CNF: `[(-i, +j), (+i, -j)]`

Bảng chân trị kiểm chứng:

| Cᵢ | Cⱼ | `(¬Cᵢ ∨ Cⱼ)` | `(Cᵢ ∨ ¬Cⱼ)` | CNF | `Cᵢ ↔ Cⱼ` |
|:-:|:-:|:-:|:-:|:-:|:-:|
| 0 | 0 | 1 | 1 | 1 | 1 |
| 0 | 1 | 1 | 0 | 0 | 0 |
| 1 | 0 | 0 | 1 | 0 | 0 |
| 1 | 1 | 1 | 1 | 1 | 1 |

### 3.3 DIFFERENT: `Cᵢ ⊕ Cⱼ`

```
Cᵢ ⊕ Cⱼ
≡ (Cᵢ ∨ Cⱼ) ∧ ¬(Cᵢ ∧ Cⱼ)
≡ (Cᵢ ∨ Cⱼ) ∧ (¬Cᵢ ∨ ¬Cⱼ)
```

CNF: `[(+i, +j), (-i, -j)]`

---

## 4. Clue đếm `Σ_{x∈R} Cₓ ⋈ k`

Gọi `m = |R|`, `x₁ … x_m` là biến của các ô trong `R` (theo thứ tự row-major).

### 4.1 Trường hợp biên (xử lý trước, cho cả hai kiểu mã hóa)

| Điều kiện | Kết quả |
|---|---|
| `AtMost(k)` với `k = m` | Hằng đúng → **không sinh clause** |
| `AtLeast(k)` với `k = 0` | Hằng đúng → **không sinh clause** |
| `AtMost(0)` | `m` unit clause `(-xₜ)` |
| `AtLeast(m)` | `m` unit clause `(+xₜ)` |
| `k > m` hoặc `k < 0` | `ClueError` (đã chặn ở mục 1.3) |

`EXACTLY(k, R)` = `AtMost(k) ∧ AtLeast(k)` (trùng clause thì loại).

### 4.2 Combinatorial (trực tiếp)

**AtMost(k):** không có `k+1` biến nào cùng đúng. Với mọi tập con `S ⊆ R`, `|S| = k+1`:

```
( ⋁_{x∈S} ¬x )
```

Số clause: `C(m, k+1)`.

**AtLeast(k):** trong mọi `m−k+1` biến phải có ít nhất một đúng (nếu không thì tối đa `k−1` biến đúng). Với mọi `S ⊆ R`, `|S| = m−k+1`:

```
( ⋁_{x∈S} x )
```

Số clause: `C(m, m−k+1) = C(m, k−1)`.

**EXACTLY(k):** `C(m, k+1) + C(m, k−1)` clause, **0 biến phụ**.

Chứng minh ngắn (đưa vào báo cáo):
- AtMost: nếu có `≥ k+1` biến đúng thì chọn `k+1` biến đó làm `S`, clause tương ứng bị sai. Ngược lại nếu `≤ k` biến đúng thì mọi `S` có ít nhất một biến sai, mọi clause đúng.
- AtLeast: nếu có `≤ k−1` biến đúng thì còn `≥ m−k+1` biến sai, chọn chúng làm `S`, clause bị sai. Ngược lại nếu `≥ k` biến đúng thì mọi `S` kích thước `m−k+1` chứa ít nhất một biến đúng (vì chỉ có `m−k` biến sai).

Kích thước tối đa: với `m ≤ 8` (vùng hàng xóm hoặc hàng/cột của lưới ≤ 5×5) thì `C(8,4) = 70` clause, rất nhỏ. Với `CELLS` lớn (ví dụ 13 ô trong lưới 5×5) có thể lên đến `C(13,7) = 1716` clause cho mỗi nửa, vẫn chấp nhận được; với `m` lớn hơn thì dùng 4.3.

**Ngưỡng chuyển cách mã hóa:** nếu tổng số clause ước lượng `> 50 000` (cấu hình được) thì encoder tự chuyển sang sequential counter cho clue đó và ghi cảnh báo.

### 4.3 Sequential counter (dạng tương đương hai chiều)

Dùng biến phụ `s[i][j]` (`1 ≤ i ≤ m`, `1 ≤ j ≤ min(i, K)`) với ý nghĩa:

```
s[i][j]  ⟺  trong x₁ … xᵢ có ít nhất j biến đúng
```

`K = k+1` cho AtMost, `K = k` cho AtLeast (đủ để quyết định); với EXACTLY dùng `K = k+1`.

Quy ước: `s[i][0] = ⊤`, `s[0][j] = ⊥` với `j ≥ 1`, `s[i][j] = ⊥` với `j > i`.

Ràng buộc định nghĩa (với `i ≥ 1`, `1 ≤ j ≤ min(i, K)`):

| Chiều | Công thức | Clause |
|---|---|---|
| ← (đủ) | `s[i−1][j] → s[i][j]` | `(-s[i−1][j] ∨ +s[i][j])` |
| ← (đủ) | `xᵢ ∧ s[i−1][j−1] → s[i][j]` | `(-xᵢ ∨ -s[i−1][j−1] ∨ +s[i][j])` (nếu `j=1` bỏ literal `s[i−1][0]`) |
| → (cần) | `s[i][j] → s[i−1][j] ∨ xᵢ` | `(-s[i][j] ∨ +s[i−1][j] ∨ +xᵢ)` |
| → (cần) | `s[i][j] → s[i−1][j] ∨ s[i−1][j−1]` | `(-s[i][j] ∨ +s[i−1][j] ∨ +s[i−1][j−1])` (nếu `j=1` clause này bỏ vì `s[i−1][0] = ⊤`) |

Sau khi thêm ràng buộc định nghĩa, các ràng buộc cardinality chỉ là unit clause trên `s[m][·]`:

| Clue | Unit clause |
|---|---|
| `AtMost(k)` | `(-s[m][k+1])` |
| `AtLeast(k)` | `(+s[m][k])` |
| `EXACTLY(k)` | cả hai: `(+s[m][k])`, `(-s[m][k+1])` |

Chi phí: khoảng `4·m·K` clause và `m·K` biến phụ; nhỏ hơn combinatorial khi `m` lớn, nhưng thêm biến phụ.

> Hạng `s[i][j]` bị `⊥` (vì `j > i`) phải được **thay trực tiếp** khi sinh clause (bỏ clause đã thỏa hoặc bỏ literal sai), không cấp biến cho nó.

Lợi ích của dạng tương đương hai chiều: thỏa I2, và **tái sử dụng được** cho `COMPARE` (mục 6.2).

### 4.4 Ví dụ dẫn xuất cho báo cáo

**Ví dụ A (combinatorial, EXACTLY):** ô `A1` ở lưới 3×3 có clue "Có đúng 1 criminal trong số hàng xóm của `A1`".

- Hàng xóm của `A1`: `B1, A2, B2` → biến `2, 4, 5`, `m = 3`, `k = 1`.
- AtMost(1): mọi tập 2 biến: `C(3,2) = 3` clause

```
(-2 ∨ -4)   (-2 ∨ -5)   (-4 ∨ -5)
```

- AtLeast(1): mọi tập `m−k+1 = 3` biến: `C(3,3) = 1` clause

```
(+2 ∨ +4 ∨ +5)
```

- Kết quả: **4 clause, 0 biến phụ**. Kiểm chứng: gán `(2,4,5) = (1,0,0)` thỏa cả 4 clause; `(1,1,0)` vi phạm `(-2 ∨ -4)`; `(0,0,0)` vi phạm `(+2 ∨ +4 ∨ +5)`.

**Ví dụ B (EXACTLY, m = 4, k = 2):** vùng `x₁..x₄` = biến `1..4`.

- AtMost(2): mọi tập 3 biến → 4 clause: `(-1 ∨ -2 ∨ -3) (-1 ∨ -2 ∨ -4) (-1 ∨ -3 ∨ -4) (-2 ∨ -3 ∨ -4)`
- AtLeast(2): mọi tập `m−k+1 = 3` biến → 4 clause: `(+1 ∨ +2 ∨ +3) (+1 ∨ +2 ∨ +4) (+1 ∨ +3 ∨ +4) (+2 ∨ +3 ∨ +4)`
- Tổng 8 clause, 6 mô hình thỏa (`C(4,2) = 6`).

**Ví dụ C (số clause theo `k`, `m = 4`):**

| k | AtMost: `C(4, k+1)` | AtLeast: `C(4, k−1)` | EXACTLY (tổng) |
|:-:|:-:|:-:|:-:|
| 0 | 4 (unit) | bỏ (hằng đúng) | 4 |
| 1 | 6 | 1 | 7 |
| 2 | 4 | 4 | 8 |
| 3 | 1 | 6 | 7 |
| 4 | bỏ (hằng đúng) | 4 (unit) | 4 |

---

## 5. PARITY *(extension 1)*

`PARITY(R, p)`: số Criminal trong `R` chẵn (`p = EVEN`) hoặc lẻ (`p = ODD`).

### 5.1 Trực tiếp (mặc định khi `m ≤ 8`)

Cấm mọi gán của `x₁..x_m` có **sai parity**. Mỗi gán bị cấm `(v₁..v_m)` sinh một clause loại đúng gán đó: literal `+xₜ` nếu `vₜ = 0`, `-xₜ` nếu `vₜ = 1`. Số clause: `2^(m−1)`, 0 biến phụ.

Ví dụ `ODD` trên `x₁, x₂, x₃` (bị cấm: các gán có số 1 chẵn: `000, 011, 101, 110`):

| Gán bị cấm | Clause |
|:-:|---|
| `000` | `(x₁ ∨ x₂ ∨ x₃)` |
| `011` | `(x₁ ∨ ¬x₂ ∨ ¬x₃)` |
| `101` | `(¬x₁ ∨ x₂ ∨ ¬x₃)` |
| `110` | `(¬x₁ ∨ ¬x₂ ∨ x₃)` |

`EVEN` tương tự, cấm các gán có số 1 lẻ.

### 5.2 Chuỗi XOR (khi `m > 8`)

Biến phụ `t₂ … t_m` với `t₁ ≡ x₁` (không cấp biến) và `tᵢ ⟺ tᵢ₋₁ ⊕ xᵢ`. Mỗi cổng XOR `t = a ⊕ b` sinh 4 clause:

```
(-t ∨ +a ∨ +b)   (-t ∨ -a ∨ -b)   (+t ∨ -a ∨ +b)   (+t ∨ +a ∨ -b)
```

Cuối cùng thêm unit: `(+t_m)` nếu `ODD`, `(-t_m)` nếu `EVEN`. Chi phí `4(m−1)` clause + 1 unit, `m−1` biến phụ; thỏa I2.

---

## 6. COMPARE *(extension 2)*

`COMPARE(L, op, R)`: `Σ_L op Σ_R` với `op ∈ {LT, LE, EQ, GE, GT}`. `L` và `R` có thể **giao nhau**; khi giao thì biến chung được tính ở cả hai tổng.

### 6.1 Trực tiếp (mặc định khi số biến phân biệt `|L ∪ R| ≤ 10`)

Gọi `U = L ∪ R` (biến phân biệt). Liệt kê mọi gán `a` của `U` (`2^|U|` gán), tính `Σ_L(a)` và `Σ_R(a)`. Gán nào **vi phạm** `op` thì sinh một clause loại đúng gán đó (giống mục 5.1).

Ví dụ: `L = {a, b}`, `R = {c}`, `op = GT` (cần `a + b > c`). Gán vi phạm là `a + b ≤ c`:

| `(a,b,c)` | `a+b` | `c` | Vi phạm? | Clause |
|:-:|:-:|:-:|:-:|---|
| `000` | 0 | 0 | có | `(a ∨ b ∨ c)` |
| `001` | 0 | 1 | có | `(a ∨ b ∨ ¬c)` |
| `011` | 1 | 1 | có | `(a ∨ ¬b ∨ ¬c)` |
| `101` | 1 | 1 | có | `(¬a ∨ b ∨ ¬c)` |
| các gán còn lại | | | không | |

Kết quả: 4 clause, 0 biến phụ.

### 6.2 Bộ đếm đơn phân (khi `|U| > 10`)

Dùng sequential counter tương đương hai chiều (mục 4.3) cho cả `L` và `R` với `K = m_L` và `K = m_R`; gọi `sL[j]` ⟺ `Σ_L ≥ j` và `sR[j]` ⟺ `Σ_R ≥ j` (các biến `s[m][j]`, quy ước `s[·][0] = ⊤`, `s[·][j] = ⊥` khi `j >` kích thước vùng). Khi đó:

| op | Điều kiện | Ràng buộc |
|---|---|---|
| `LT` (`Σ_L < Σ_R`) | với mọi `j ∈ [0, m_L]`: `Σ_L ≥ j → Σ_R ≥ j+1` | `(-sL[j] ∨ +sR[j+1])` với `j = 1..m_L`; thêm unit `(+sR[1])` cho `j = 0` |
| `LE` | với mọi `j ∈ [1, m_L]`: `Σ_L ≥ j → Σ_R ≥ j` | `(-sL[j] ∨ +sR[j])` |
| `GT`, `GE` | đổi vai `L` và `R` của `LT`, `LE` | |
| `EQ` | `LE` hai chiều | cả `(-sL[j] ∨ +sR[j])` và `(-sR[j] ∨ +sL[j])` |

Khi chỉ số vượt kích thước vùng, thay `sR[j] = ⊥` (literal bị bỏ khỏi clause) hoặc `sL[j] = ⊥` (clause thỏa, bỏ).

> Cách 6.2 chỉ đúng nếu `s` là tương đương hai chiều (không chỉ một chiều). Cách 6.1 không cần lưu ý này.

---

## 7. Kiểm chứng bắt buộc: `semantics = CNF`

Với mỗi loại clue (6 cơ bản + 2 extension) và mỗi vùng mẫu trên lưới 3×3 (`N² = 9` biến, `2⁹ = 512` gán):

```
với mọi gán a ∈ {0,1}^9:
    expected = semantics.holds(clue, a, n)
    actual   = tồn tại gán biến phụ b: CNF(clue) thỏa bởi (a, b)
    assert expected == actual
```

Với `n_aux = 0`: `actual` là đánh giá trực tiếp CNF trên `a`. Với biến phụ: tìm `b` bằng DPLL của M4 với `assumptions = các literal của a`, hoặc (nếu chưa có DPLL) bằng vét cạn trên biến phụ (số biến phụ nhỏ).

Chi tiết các ca: xem [`TEST_CASES.md`](TEST_CASES.md), nhóm `CNF-*`.

---

## 8. Chọn cách mã hóa

| Tình huống | Cách mã hóa |
|---|---|
| Vùng `Count` có `C(m, ·) ≤ 50 000` clause | Combinatorial (mặc định) |
| Quá ngưỡng | Sequential counter, ghi cảnh báo |
| `--encoding sequential` | Ép dùng sequential cho mọi clue đếm |
| `PARITY`, `m ≤ 8` | Trực tiếp; `m > 8` chuỗi XOR |
| `COMPARE`, `|U| ≤ 10` | Trực tiếp; ngược lại bộ đếm đơn phân |

Hai cờ cho thực nghiệm (xem [`EXPERIMENTS.md`](EXPERIMENTS.md)): `--encoding {combinatorial,sequential}`.

---

## 9. Danh mục kiểm tra khi review (M4 review code M3)

- [ ] Biến chính ánh xạ đúng `r·N + c + 1`; biến phụ không trùng.
- [ ] Mọi clue đi qua `RegionResolver.cells` (không tự tính neighbors).
- [ ] Các trường hợp biên của mục 4.1 đúng (k = 0, k = m, k = 0 cho AtLeast).
- [ ] Không sinh clause rỗng ngoài ý muốn (clause rỗng nghĩa là UNSAT; chỉ hợp lệ nếu clue tự mâu thuẫn, mà điều đó đã bị chặn ở bước validate).
- [ ] `semantics.holds` không import `encoder`.
- [ ] Test `semantics = CNF` chạy trên đủ 512 gán cho mọi loại clue.
- [ ] Thống kê `n_primary`, `n_aux`, `n_clauses` in đúng.
