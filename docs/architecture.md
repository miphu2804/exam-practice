# Kiến trúc

## Module Python (`src/exam_practice/`)

| Module | Vai trò | I/O? |
|---|---|---|
| `cli.py` | Tham số dòng lệnh, chọn mode: crawl / register / sync / rebuild / list / serve | có |
| `fetch.py` | `httpx` session, cookie (Chrome qua `pycookiecheat` import lười, `cookies.txt`, `--cookie`), `LoginRequired` | mạng |
| `crawler.py` | Tải thread (mọi trang), trang media của từng ảnh, ảnh → `exams/<code>/raw/` + `images/` | mạng + đĩa |
| `parse.py` | HTML → `Attachment`, `Comment`, `Vote`, `Answer`; luật đối chiếu đáp án | **thuần** |
| `build.py` | manifest + raw → `data.json`/`data.js`/`exam.json`, `index.json`/`index.js`, khung `view` từ ảnh | đĩa, không mạng |
| `registry.py` | Đọc/ghi `exams/registry.json` (sổ đề cho `--sync`) | đĩa |
| `catalog.py` | Đổi tên / xóa đề (thư mục, manifest, sổ, index) | đĩa |
| `server.py` | FastAPI: `/api/*`, phục vụ `exams/` + `src/web/` (local) hoặc chuyển hướng sang Blob (hosted) | HTTP |
| `blobstore.py` | Upload đề lên Vercel Blob, liệt kê index từ Blob | mạng |
| `paths.py` | Vị trí thư mục; trên Vercel `EXAMS = /tmp/exams` | — |

Lối vào: `crawl.py` (gọi `cli.main`), `api/index.py` (Vercel function, import
`server.app`), `uvicorn exam_practice.server:app`.

## Hai chế độ chạy

Chế độ do `server.app` chọn lúc import: có `BLOB_READ_WRITE_TOKEN` → hosted.

| | Local (`./dev.sh`, `--serve`) | Hosted (Vercel) |
|---|---|---|
| Cookie crawl | Chrome của máy / `cookies.txt` / ô nhập | **bắt buộc** người dùng dán `xf_user` của họ |
| Nơi lưu đề | `exams/<code>/` | ghi tạm `/tmp/exams/<code>/` → upload Blob `exams/<code>/…` → xóa tmp |
| `GET /exams/index.json` | file tĩnh | dựng từ danh sách Blob (`blobstore.index`) |
| `GET /exams/<path>` | file tĩnh | `307` sang URL public của Blob |
| Đổi tên / xóa | được | `403` (khách nào cũng xóa được của mọi người) |
| Khóa crawl | một khóa toàn cục, trùng → `409` | không khóa (mỗi request một instance) |
| `GET /api/info` | `{"hosted": false}` | `{"hosted": true}` — web dựa vào đây để ẩn nút / bắt cookie |

Web phục vụ ở hosted là CDN của Vercel (`outputDirectory: src/web`), không qua Python.

## API

| Route | Mô tả |
|---|---|
| `GET /api/info` | `{hosted}` |
| `POST /api/crawl` | body `{url, name?, minutes?, cookie?}` → crawl + build + (hosted: publish). Lỗi: `400` URL/crawl sai, `401` thiếu/hết cookie, `409` đang bận, `500` lỗi khác |
| `PATCH /api/exams/{code}` | body `{title}` — đổi tên (local) |
| `DELETE /api/exams/{code}` | xóa đề (local) |

`server.py` chỉ nghe `127.0.0.1` khi chạy local vì request có thể mang cookie đăng nhập.

## Nguyên tắc khi sửa

- Logic mới về đáp án → `parse.py` (thuần, test bằng chuỗi). Định dạng đầu ra → `build.py`.
  Đừng đưa mạng vào hai file này: `--rebuild` và test phụ thuộc vào điều đó.
- Thêm trường dữ liệu cho web → `build._question` rồi `uv run crawl.py --rebuild`
  (đề cũ không cần crawl lại).
- `create_app(crawl, hosted=…)` nhận hàm crawl qua tham số để test thay bằng fake.
