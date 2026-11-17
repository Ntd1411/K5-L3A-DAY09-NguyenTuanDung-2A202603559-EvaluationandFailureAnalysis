# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-014 --seed 11
python -m lab9.trace_case --shape fixed --claim C-014 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

---

## Chi tiết Case: `seeded_regression C-014@11` (FM-05: pre_deducted)

### 1. Diễn biến Trace trên `seeded_regression C-014@11`
- **Event 1 (`handoff`)**: `{"claim_id": "C-014", "allowed_tools": ["lookup_order", "lookup_policy", "compute_compensation"], "principal_scope": "owner_order_only"}` — *Hợp lệ theo allowlist.*
- **Event 2 (`investigator`)**: `{"lookup_order": {"order_id": "O-515", "status": "delivered_late", "delay_days": 5, "shipping_fee_vnd": 30000, "paid_vnd": 200000, "damage_verified": true}}` — *Đọc đúng DB.*
- **Event 3 (`quote`)**: `{"amount_vnd": 150000, "reason": "entitled", "clause_ids": ["SHIP-LATE-03", "DMG-04"], "parts": {"SHIP-LATE-03": 30000, "DMG-04": 150000}}` — *Tính entitlement quote 150.000đ chính xác.*
- **Event 4 (`refund_history`)**: `{"refund_count": 1, "refunded_vnd": 30000}` — *Đọc lịch sử đã hoàn 30.000đ.*
- **Event 5 (`proposal`)**: `{"amount_vnd": 120000}` ← **BƯỚC SAI ĐẦU TIÊN (FIRST WRONG STEP)**: Agent tự trừ 30.000đ lịch sử khỏi quote 150.000đ để ra proposal 120.000đ. Khi gọi host `durability.issue_refund`, host lại trừ `already_refunded_vnd = 30000` thêm một lần nữa, khiến ledger thực tế chỉ ghi nhận `90.000đ` thay vì `120.000đ`.
- **Event 6 (`reply`)**: `{"text": "Dạ, LogiX đã hoàn 120.000đ cho đơn O-515."}` ← Kéo theo **FM-08**: Reply báo 120.000đ nhưng ledger chỉ có 90.000đ.

---

## Bảng phân tích Case theo mẫu chuẩn

| Trường | Nội dung |
|---|---|
| **Trial** | `seeded_regression C-014@11`, item `E-014` trong eval set `8d5681967c1a`; run ID `E-seeded_regression-20261117-8d56` trong `src/reports/eval_seeded_regression.json`. Trace run: `R-seeded_regression-C-014-s11.json`. |
| **Triệu chứng** | Lab 8 grader báo `FAIL (proposal_mismatch)`.<br>Code grader: `refund_amount_correct = False` (ledger ghi 90.000đ ≠ nhãn 120.000đ); `proposal_amount_correct = False` (proposal 120.000đ ≠ nhãn 150.000đ); `reply_ledger_consistent = False` (reply phát biểu 120.000đ trong khi ledger thực tế là 90.000đ).<br>Lưu ý: reply phát ngôn đúng số tiền nhãn (120.000đ) nên nếu chỉ nhìn văn bản trả lời sẽ bị đánh lừa là pass! |
| **Bước sai đầu tiên** | **Event 5: kind = `proposal`, payload = `{"amount_vnd": 120000}`**.<br>Agent tự ý lấy quote (150.000đ) trừ đi lịch sử refund (30.000đ) rồi mới gửi cho host. |
| **Vì sao là bước *đầu tiên*** | - Event 1: Handoff đúng schema và ranh giới quyền `owner_order_only`.<br>- Event 2: Investigator đọc đúng thông tin đơn hàng và policy từ DB.<br>- Event 3: Tool compensation tính quote 150.000đ khớp chuẩn nghiệp vụ.<br>- Event 4: Lịch sử hoàn tiền 30.000đ đọc từ DB là chính xác.<br>Host (`lab8/durability.py`) đã có cơ chế tự trừ lịch sử (`amount -= already_refunded_vnd`). Agent phải chuyển nguyên vẹn quote 150.000đ. Việc trừ trước ở Event 5 khiến khoản 30.000đ bị trừ 2 lần (double deduction). Event 6 reply chỉ là hệ quả. |
| **Failure mode** | **FM-05: `pre_deducted` — trừ trước khi được duyệt** (kéo theo **FM-08: `misreport`** ở bước reply). |
| **Đối chứng (`fixed`)** | Cùng trial trên shape `fixed` (`fixed C-014@11`):<br>- Event 1–3 giống hệt.<br>- Không hề có event `refund_history` và event `proposal` của agent.<br>- Proposal 150.000đ gửi thẳng cho host, host tự trừ 30.000đ lịch sử → ledger ghi đúng 120.000đ.<br>- Event 4 `reply`: `"Dạ, LogiX đã hoàn 120.000đ cho đơn O-515."` khớp hoàn toàn với ledger.<br>- Grader: PASS (ok). |
| **Regression test** | File `src/tests/test_lab9_trace_case.py` (nằm trong marker `student`, chạy tự động ở CI gate):<br>1. `test_trace_case_c014_first_wrong_step`: Khóa chặt thứ tự event 1-5 và bắt lỗi proposal bị trừ trước thành 120.000đ.<br>2. `test_trace_case_c014_graders_catch_error`: Xác nhận các evaluator `ProposalAmountCorrect`, `RefundAmountCorrect`, và `ReplyLedgerConsistent` đều đánh FAIL trên `seeded_regression`.<br>3. `test_trace_case_c014_fixed_passes`: Xác nhận cùng bộ grader PASS trên bản `fixed`. |
| **Chưa chắc chắn** | MockLLM chạy tất định nên seed 11-55 đều xuất hiện lỗi như nhau. Với LLM production thực tế có temperature > 0, cần theo dõi xác suất xảy ra lỗi tính toán này. Ngoài ra trace chỉ ghi nhận sự kiện cấp ứng dụng, không phản ánh tư duy nội tại của mô hình nếu không có reasoning trace. |

---

## Đối chứng phụ: `seeded_regression C-002@11` (FM-03: ticket_trust)
- **Bước sai đầu tiên**: Event 3: `model_override {"delay_days": 5}` ghi đè `delay_days = 2` authoritative đọc từ DB tại Event 2, biến một claim không đủ điều kiện (đáng lẽ `denied`, refund = 0) thành `resolved` và giải ngân 20.000đ trái luật.
- **Đối chứng `fixed C-002@11`**: Không có `model_override`, từ chối bồi thường đúng quy định, ledger = 0, status = `denied`.
- **Regression test đi kèm**: `test_trace_case_c002_first_wrong_step` và `test_trace_case_c002_graders_catch_error` trong `src/tests/test_lab9_trace_case.py`.
