# Pipeline crawl → parse → build

## 1. Crawl (`crawler.crawl_thread`)

1. Tải mọi trang của thread → `raw/thread-p<n>.html`; `parse.thread_meta` lấy tiêu đề,
   `parse.parse_attachments` lấy danh sách ảnh đính kèm của bài đầu.
2. Mỗi ảnh: tải về `images/`, tải trang media gallery (nơi người dùng bình luận đáp
   án) → `raw/media-*.html`.
3. Ghi `raw/manifest.json` (url, tiêu đề, danh sách attachment + đường dẫn raw).
   Từ đây trở đi không cần mạng.

Thứ tự câu: ảnh có số trong tên (`Q46.webp`, `Câu 12.png`) được xếp theo số đó khi
*mọi* ảnh đều có số (người đăng hay đính kèm lộn thứ tự); không thì giữ thứ tự đăng.

## 2. Parse — đối chiếu đáp án (`parse.py`)

`collect_votes(comments, page_question)` biến mỗi bình luận thành `Vote(question,
author, letters, text)`:

- **Entry** — `_ENTRY_RE`: `Câu 12: A`, `12A`, `1. B, C` → phiếu cho đúng câu ghi trong bình luận.
- **Bare** — `_BARE_RE`: bình luận ngắn `A`, `A,B`, "mình chọn A" → phiếu cho câu của
  trang media đó (`page_question`).
- `text` là đoạn trích dùng làm evidence: bare giữ nguyên bình luận; entry cắt
  `excerpt()` ±40 ký tự quanh đúng số câu (tối đa `EXCERPT_CHARS = 140`, có `…`).
  `Vote.text` có `compare=False` nên không ảnh hưởng so sánh/khử trùng phiếu.

`resolve_answers(votes, total)`:

- Mỗi `(câu, tác giả)` chỉ tính một phiếu; phiếu sau thắng (người ta hay sửa lại).
- Đáp án = **tập** chữ cái xuất hiện nhiều nhất; hòa thì ưu tiên tập nhỏ hơn.
- `multi` = tập thắng có ≥ 2 chữ. `contested` = á quân ≥ 75% phiếu của tập thắng.
- `evidence` = các phiếu đã khử trùng của câu đó.

Muốn đổi luật (ngưỡng tranh chấp, cú pháp mới): sửa ở đây, thêm case vào
`tests/test_parse.py`, rồi `uv run crawl.py --rebuild` và đọc bảng tổng kết.

## 3. Build (`build.py`)

`build_exam(manifest, exam_dir)` ghép đáp án với attachment, tính `stats`, tính `view`
(khung chứa chữ chung của mọi ảnh, để web phóng đúng vùng có chữ, bỏ watermark góc),
rồi `write_exam` ghi:

- `data.json` + `data.js` (`window.EXAM_DATA = …`, để mở được cả bằng `file://`)
- `exam.json` — tóm tắt cho danh sách đề
- `write_index` gom mọi `exam.json` → `exams/index.json` + `index.js` (`window.EXAM_INDEX`)

## Định dạng `data.json`

```jsonc
{
  "code": "hcm202-su26-re",
  "title": "Đề Thi FE - HCM202 - SU26 - RE",
  "source": "https://fuoverflow.com/threads/…/",
  "generated": "2026-10-10T…",
  "default_duration_min": 45,
  "choices": ["A", "B", "C", "D"],
  "view": { "x": 0, "y": 0, "w": 1280, "h": 420, "width": 1600, "height": 900 }, // khung chữ + cỡ ảnh; có thể null
  "stats": { "questions": 60, "answered": 60, "contested": 2, "multi": 1, "votes": 387 },
  "questions": [{
    "n": 1,
    "image": "images/q01.webp",                           // tương đối với exams/<code>/
    "source": "…/post-5495#attachment-147969",            // link "bài gốc"
    "media": "…/media/…70478/",                           // link "bình luận"
    "type": "single",
    "answer": ["D"],                                      // [] = chưa có đáp án
    "multi": false, "pick": 1, "contested": false,
    "letter_votes": { "A": 0, "B": 0, "C": 0, "D": 8 },
    "vote_count": 8,
    "evidence": [{ "author": "Vy Vu", "letters": ["D"], "text": "d" }]
  }]
}
```

Thêm trường: sửa `build._question`, cập nhật khối này, đề cũ chạy `--rebuild`. Web phải
chịu được đề cũ thiếu trường (ví dụ `q.evidence || []`).
