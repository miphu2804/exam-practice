# AGENTS.md

`exam-practice`: một dự án dùng chung cho nhiều mã đề FuOverflow. Code trong
`src/`, dữ liệu mỗi đề trong `exams/<code>/`.

## Mục tiêu

Một lệnh crawl (`uv run crawl.py <thread-url>`) tải ảnh đề + bình luận, tự đối
chiếu đáp án theo bình chọn nhiều nhất, ghi `exams/<code>/`, cập nhật index. Web
tĩnh trong `src/web/` để làm bài; backend FastAPI (`server.py`) có `POST /api/crawl`
cho ô crawl đề. Không có dữ liệu mẫu: mọi đề là bản crawl thật.

## Lệnh

```bash
uv sync
uv run crawl.py <thread-url>        # crawl + đối chiếu + cập nhật index
uv run crawl.py <thread-url> --name "Tên đề" --register   # đặt tên + lưu vào sổ
uv run crawl.py --sync --ttl-days 7                       # cron: setup/làm mới mọi đề
uv run crawl.py --rebuild [CODE]    # dựng lại từ exams/*/raw, không mạng
uv run crawl.py --list
./dev.sh                            # uvicorn :8000 + Vite :5173 -> http://localhost:5173/
uv run crawl.py --serve             # chỉ backend (kèm web) tại http://localhost:8000/
uv run pytest -q                    # gồm E2E web bằng Playwright + Chrome cài sẵn (~30 s)
uv run pytest -q --ignore tests/test_web_e2e.py   # chỉ unit, nhanh
```

## Quy ước

- I/O nằm ở `fetch.py`, `crawler.py`, `blobstore.py` và `server.py` (local chỉ nghe 127.0.0.1;
  có `BLOB_READ_WRITE_TOKEN` là chế độ hosted Vercel: cookie bắt buộc từ người dùng, đề trong Blob, cấm đổi tên/xóa); `parse.py` và `build.py` thuần/không mạng
  để chạy lại trên raw và test bằng fixture.
- Web tĩnh, không build step (Vite chỉ là dev server, proxy `/api` + `/exams`); ảnh tham chiếu bằng đường dẫn tương đối từ
  `exams/<code>/` (app tiền tố `../../exams/<code>/`).
- Giao diện theo tinh thần skill `design-taste-frontend`: token màu, dark/light,
  không gradient/emoji, hạn chế motion, tôn trọng `prefers-reduced-motion`.
- Ghi chú/tiến độ người dùng chỉ ở localStorage (khoá `notes:<code>`), không lên server.
- Không commit: `cookies.txt`, `exams/*/raw/`, `exams/*/images/`,
  `exams/index.json`, `exams/index.js`.
