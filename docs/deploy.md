# Deploy

## Local / chia sẻ trong máy

```bash
uv sync && npm install
./dev.sh                     # uvicorn :8000 + Vite :5173
uv run crawl.py --serve      # chỉ backend, phục vụ luôn web tại :8000
```

## Vercel + Blob

Các file liên quan:

- `vercel.json` — `framework: null`, không install/build, `outputDirectory: src/web`
  (CDN phục vụ web), function `api/index.py` (`maxDuration: 300`, kèm `src/exam_practice/**`),
  rewrite `/api/*` và `/exams/*` về function.
- `api/index.py` — thêm `src` vào `sys.path`, export `app`.
- `.vercelignore` — loại `cookies.txt`, `.env`, `exams/`, `.venv/`, `node_modules/`, `tests/`, cache và log.
- Phụ thuộc Python lấy từ `pyproject.toml`/`uv.lock` (gói `vercel` cho Blob SDK).

Project `exam-practice` đã nối repo GitHub: push lên `main` tự deploy production, nhánh
khác thành preview. Vercel Authentication đã tắt (ai cũng mở được, kể cả preview).

Lần đầu:

```bash
npx vercel link
npx vercel blob create-store exam-practice --access public --yes   # tự thêm BLOB_READ_WRITE_TOKEN
npx vercel deploy --prod
```

Cấu hình chỉ đọc từ biến môi trường (`app_config.py`, pydantic-settings); không có file
`.env`. Local không cần biến nào vì mọi biến đều có mặc định, nên `./dev.sh` chạy được ngay.

| Biến | Ý nghĩa |
|---|---|
| `BLOB_READ_WRITE_TOKEN` | Có → chế độ hosted. Store id là trường thứ 4 (tách `_`) của token, dùng dựng URL public |
| `LOG__LEVEL` | Mức log của `logging` (mặc định `INFO`: bắt đầu/xong crawl, báo cáo build, traceback khi lỗi 500) |
| `VERCEL` | Vercel tự đặt → `paths.EXAMS = /tmp/exams` |

## Giới hạn khi hosted (biết trước, chưa xử lý)

- Ảnh đề trên Blob là **public** (ai có URL đều xem được).
- Crawl lại ghi đè cùng đường dẫn; CDN của Blob có thể trả bản cũ tối đa 60 s
  (`MAX_AGE_SECONDS` trong `exams/blob_storage.py`).
- Hai crawl cùng một thread trên cùng instance cùng lúc có thể giẫm nhau trong `/tmp`.
- FuOverflow có thể chặn IP của Vercel; khi đó crawl local rồi chạy `--sync` từ máy.
- Không có đổi tên/xóa trên web; dọn Blob bằng dashboard Vercel hoặc `npx vercel blob`.
- Một crawl phải xong trong 300 s (giới hạn function).
