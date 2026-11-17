# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Có | dùng cho tiêu chí tone |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không | loại khỏi gate |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | H-008 | PASS | FAIL | Người | “em”, “nha”, “check giúp em” quá suồng sã; rubric phải nêu rõ xưng hô CSKH được phép. |
| 2 | H-029 | PASS | FAIL | Người | “không cần nhắn thêm” là giọng ra lệnh; thêm ví dụ negative về câu lịch sự ở đầu nhưng áp đặt ở cuối. |
| 3 | H-042 | FAIL | PASS | Người | Câu ngắn nhưng đủ thông tin và lịch sự; rubric không được bắt buộc xin lỗi trong mọi reply. |
| 4 | H-051 | FAIL | PASS | Người | Từ “refund” được chuẩn CS LogiX cho phép; đưa danh sách thuật ngữ Anh–Việt được chấp nhận vào rubric. |
| 5 | H-063 | PASS | FAIL | Người | “sẽ hoàn thêm” là lời hứa ngoài kết quả hệ thống; rubric phải cấm cam kết không có trong ledger. |
| 6 | H-081 | FAIL | PASS | Judge | Ghi chú nguồn xác nhận nhãn người đọc nhầm ticket; sửa nhãn và yêu cầu adjudication khi human/judge bất đồng. |
| 7 | HL-015 | PASS | FAIL | Người | Số tiền 55.000đ khác ledger 40.000đ; helpfulness phải kiểm factual grounding trước độ trôi chảy. |
| 8 | HL-047 | PASS | FAIL | Người | “xử lý rồi” không nói kết quả cụ thể và xưng hô suồng sã; thêm yêu cầu nêu outcome có thể kiểm chứng. |

## Kết luận
- `tone_ok` được dùng vì ma trận nhầm lẫn `tp=24, fp=4, fn=6, tn=66` cho P=0.857, R=0.800 và κ=0.757, đều vượt sàn; tỉ lệ FAIL quan sát 0.28 được Rogan–Gladen hiệu chỉnh thành 0.30.
- `helpful` bị loại khỏi gate: dù P=1.000, ma trận `tp=9, fp=0, fn=21, tn=70` cho R=0.300 và κ=0.375, nghĩa là judge bỏ sót 70% lỗi; tỉ lệ FAIL quan sát 0.09 cũng bị đánh giá thấp hơn nhiều so với mức hiệu chỉnh 0.30.
- Không dùng judge helpful để chấm tiền hoặc tính đúng đắn: các case HL-015/016/020 cho thấy văn phong trôi chảy che được số tiền sai, trong khi tiền phải do code grader đọc ledger.
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới, adjudication và một held-out set thật trước khi thay rubric hoặc model judge.
