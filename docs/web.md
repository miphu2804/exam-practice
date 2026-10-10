# Frontend `src/web/`

Ba file, không framework, không build: `index.html` (khung + header), `styles.css`
(token màu), `app.js` (một IIFE). Đọc `app.js` từ trên xuống theo các khối comment.

## Nạp dữ liệu

`loadJson(path, key)` thử `<script src=….js>` trước (đặt `window.EXAM_INDEX` /
`window.EXAM_DATA`), hỏng thì `fetch` bản `.json`; luôn kèm `?t=` để không dính cache
sau khi crawl lại. Đường dẫn ảnh: `../../exams/<code>/<image>` (`img(q, path)`).

`boot()` → áp theme → `GET /api/info` (lưu `state.hosted`) → nạp index → `renderPicker()`.

## Màn hình

| Hàm | Màn |
|---|---|
| `renderPicker` | Kho đề: ô crawl (`crawlForm`), thẻ đề (`examCard`), trộn đề (`mixForm`, khi ≥ 2 đề) |
| `renderStart` | Màn bắt đầu: thống kê, chế độ, thứ tự câu, thời gian, nút Ghi chú |
| `renderQuiz` / `paint` | Làm bài: ảnh, đáp án, `feedback` + `evidence`, ghi chú, lưới câu |
| `renderResult` / `reviewItem` | Kết quả + xem lại, lọc đúng/sai/chưa làm |
| `renderNotes` | Danh sách câu có ghi chú, luyện lại, xuất/nhập JSON |

`quizChrome(on)` bật/tắt cụm điều khiển làm bài trên header (`#quiz-controls`,
`#timebar`); nút theme luôn hiện.

## State và danh tính câu

`state.data.questions` là danh sách câu đang làm, `state.queue` là thứ tự đi qua
(số `n`), `state.answers: Map<n, Set<letter>>`, `state.checked` là các câu đã chấm
(chế độ luyện tập).

Đề trộn gán thêm cho mỗi câu `code` (đề gốc), `orig` (số câu gốc), `view` (khung của đề
gốc) và đánh số lại `n = 1..N`. Vì thế **luôn dùng helper**, đừng đọc thẳng:

- `examOf(q)` — mã đề chứa ảnh/ghi chú của câu
- `origin(q)` — số câu gốc (khóa ghi chú)
- `qLabel(q)` — nhãn hiển thị (`Câu 12 · hcm202-…` khi trộn)

## Tính năng

- **Trộn đề** (`submitMix`): nạp `data` của từng đề đã chọn, gộp, `shuffle`, cắt `count`,
  đánh số lại. `state.data.code = "mix"`, `mixed = [codes]`, thời gian mặc định
  `max(5, ceil(count × 0.75))` phút.
- **Xáo câu** (chip `data-order`): `start()` xáo `state.queue` (Fisher–Yates);
  `state.shuffled` làm lưới câu hiện số thứ tự thay vì số gốc (tooltip là `qLabel`).
- **Evidence** (`evidence(q)`): `<details>` liệt kê bình luận; `data-tone=agree|differ`
  so với đáp án; tự mở khi câu `contested`. Dùng ở cả `feedback` và `reviewItem`.
- **Ghi chú**: `localStorage["notes:<code>"] = {origNumber: text}`, mỗi trình duyệt
  một bản, không gửi lên server. Xuất/nhập là file JSON `{code: {n: text}}`, nhập thì
  gộp đè.
- **Theme**: `localStorage.theme` ∈ `"" | "light" | "dark"`; `applyTheme` đặt
  `data-theme` trên `<html>`. Mọi truy cập storage đều bọc `try` (chế độ riêng tư).

## CSS

Token ở `:root` dùng `light-dark(<sáng>, <tối>)` + `color-scheme: light dark`;
`[data-theme=light|dark]` ghim `color-scheme`. Màu mới → thêm token, đừng viết màu
cứng. Quy ước giao diện (AGENTS.md): không gradient, không emoji, motion tối thiểu,
tôn trọng `prefers-reduced-motion`. Có breakpoint `max-width: 600px` cho điện thoại.

## Phím tắt

A–D / 1–4 chọn, ← → chuyển câu, Enter kiểm tra / câu tiếp, P tạm dừng. Chỉ bắt khi
đang làm bài (`#quiz-controls` hiện) và con trỏ không ở ô nhập.
