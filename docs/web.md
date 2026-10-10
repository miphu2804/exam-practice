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
| `renderPicker` | Kho đề: ô crawl (`crawlForm`), thẻ đề (`examCard`), Ôn lại (`reviewHub`), trộn đề (`mixForm`, khi ≥ 2 đề) |
| `renderBank` | Ôn lại câu sai / ghi chú gom từ mọi đề, luyện lại |
| `renderStart` | Màn bắt đầu: thống kê, chế độ, thứ tự câu, thời gian, nút Ghi chú |
| `renderQuiz` / `paint` | Làm bài: trái là ảnh (khung `.frame` cao cố định) + đáp án (kèm số lượt chọn khi đã chấm) + `feedback`; phải là lưới câu, Trước/Sau, ghi chú + nút Lưu |
| `renderResult` / `reviewItem` | Kết quả + xem lại, lọc đúng/sai/chưa làm, nút về kho đề; "Làm lại" đề trộn bốc bộ mới |
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

- **Trộn đề** (`submitMix`): `loadPool` nạp `data` của từng đề đã chọn, gộp, `shuffle`,
  `drawMix` bốc `count` câu, ưu tiên câu chưa gặp (`localStorage["mix:seen"]`, hết vòng thì
  làm lại từ đầu) để các lượt trộn không lặp câu cũ; `useMixed` đánh số lại. `state.data.code = "mix"`, `mixed = [codes]`, thời gian mặc định
  `max(5, ceil(count × 0.75))` phút.
- **Xáo câu** (chip `data-order`): `start()` xáo `state.queue` (Fisher–Yates);
  `state.shuffled` làm lưới câu hiện số thứ tự thay vì số gốc (tooltip là `qLabel`).
- **Evidence** (`evidence(q)`): `<details>` liệt kê bình luận; `data-tone=agree|differ`
  so với đáp án; tự mở khi câu `contested`. Dùng ở cả `feedback` và `reviewItem`.
- **Ghi chú**: `localStorage["notes:<code>"] = {origNumber: text}`, mỗi trình duyệt
  một bản, không gửi lên server. Xuất/nhập là file JSON `{code: {n: text}}`, nhập thì
  gộp đè.
- **Câu sai**: `localStorage["wrong:<code>"] = {origNumber: [letters]}`. `recordAttempt`
  ghi khi chấm (luyện tập) hoặc khi nộp (thi thử): sai thì lưu lựa chọn, đúng thì xóa.
  Nút "Đã nắm" (`forgetWrong`) xóa tay.
- **Ôn lại** (`reviewHub` → `openBank`): thẻ "câu làm sai" / "câu có ghi chú" đếm trên mọi
  đề trong index; mở thì nạp các câu đó thành một bộ trộn (`code` = `wrong`/`notes`) để xem
  lại hoặc luyện.
- **Crawl** (`submitCrawl` → `streamCrawl`): đọc NDJSON từ `/api/crawl/stream`, cập nhật
  `<progress id="crawl-progress">` (chưa biết tổng thì ở trạng thái indeterminate).
- **Theme**: `localStorage.theme` ∈ `"" | "light" | "dark"`; `applyTheme` đặt
  `data-theme` trên `<html>`. Mọi truy cập storage đều bọc `try` (chế độ riêng tư).

## CSS

Ảnh câu nằm trong `.quiz .frame` cao cố định (`container-type: size`); ảnh crop rộng
`min(100cqw, 100cqh × --ratio)` nên đổi câu không xô lệch đáp án. Dưới 900px khung về
`height: auto`.

Token ở `:root` dùng `light-dark(<sáng>, <tối>)` + `color-scheme: light dark`;
`[data-theme=light|dark]` ghim `color-scheme`. Màu mới → thêm token, đừng viết màu
cứng. Quy ước giao diện (AGENTS.md): không gradient, không emoji, motion tối thiểu,
tôn trọng `prefers-reduced-motion`. Có breakpoint `max-width: 600px` cho điện thoại.

## Phím tắt

A–D / 1–4 chọn, ← → chuyển câu, Enter kiểm tra / câu tiếp, P tạm dừng. Chỉ bắt khi
đang làm bài (`#quiz-controls` hiện) và con trỏ không ở ô nhập.
