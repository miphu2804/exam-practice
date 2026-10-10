# Bảo trì

## Test

```bash
uv run pytest -q                                   # tất cả, gồm E2E (~30 s)
uv run pytest -q --ignore tests/test_web_e2e.py    # chỉ unit, nhanh
```

| File | Phủ |
|---|---|
| `test_parse.py` | Cú pháp bình luận, luật đối chiếu, evidence/excerpt |
| `test_build.py` | manifest → `data.json`, `view`, index |
| `test_registry.py`, `test_catalog.py` | Sổ đề, đổi tên/xóa |
| `test_server.py` | API local + hosted (Blob được thay bằng fake) |
| `test_web_e2e.py` | Playwright + Chrome cài sẵn: tự sinh đề giả (`write_exam`) rồi bấm thật |

E2E cần Google Chrome trên máy. Thêm trường dữ liệu mới thì cập nhật `write_exam`
trong `test_web_e2e.py` để fixture giống đề thật.

## Việc hay gặp

**FuOverflow đổi markup / đáp án lạ.** Mở `exams/<code>/raw/media-*.html`, sửa
selector (`_COMMENT_SELECTORS`, `parse_attachments`) hoặc regex (`_ENTRY_RE`, `_BARE_RE`)
trong `parse.py`, thêm case vào `test_parse.py`, chạy `uv run crawl.py --rebuild <code>`
và đọc bảng tổng kết. Không cần crawl lại.

**Cookie hết hạn** (`401` / `LoginRequired`). Đăng nhập lại FuOverflow trên Chrome,
hoặc thay `cookies.txt`, hoặc truyền `--cookie 'xf_user=…'`.

**Thêm trường cho web.** `build._question` → `--rebuild` → dùng trong `app.js` với
giá trị mặc định cho đề cũ → cập nhật [pipeline.md](pipeline.md#định-dạng-datajson).

**Thêm màn / nút.** Theo mẫu `render*` trong `app.js`; màu qua token trong
`styles.css`; kiểm tra cả sáng và tối, và màn ≤ 600 px.

**Cron làm mới đề.** `uv run crawl.py --sync --ttl-days 7` đọc `exams/registry.json`.

## Không commit

`cookies.txt`, `exams/*/raw/`, `exams/*/images/`, `exams/index.json`, `exams/index.js`
(đã có trong `.gitignore`). Cookie là phiên đăng nhập của người dùng: đừng log, đừng
gửi đi đâu ngoài FuOverflow.

## Nhật ký

Việc đã xong ghi vào `PROGRESS.md` (mới nhất trên cùng, giữ 10 mục); vướng mắc chưa
giải quyết ghi `BLOCKERS.md`.
