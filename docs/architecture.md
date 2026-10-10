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
| `main.py` | Composition root: `create_app(configuration, crawl_exam)` chọn storage, gắn `exam_service`, `exam_storage`, `hosted` vào `app.state`, mount `exams/` + `src/web/` (local); export `app` | đĩa khi khởi động |
| `app_config.py` | `AppConfig` (pydantic-settings): `BLOB_READ_WRITE_TOKEN` (có → hosted), `LOG__LEVEL` (mặc định `INFO`); chỉ đọc biến môi trường | — |
| `exams/schema.py` | Model request/response của `/api/*`; `thread_url` kiểm tra link thread | — |
| `exams/errors.py` | `StorageBusy` (→ `409`), `ReadOnlyStorage` (→ `403`) | — |
| `exams/storage.py` | Protocol `ExamStorage`: giao diện lưu đề (Strategy) | — |
| `exams/exam_service.py` | Quy trình crawl / đổi tên / xóa, giống nhau ở mọi storage | qua crawler và storage |
| `exams/local_storage.py` | `LocalExamStorage`: khóa crawl, `registry.json`, index, catalog trên `exams/` | đĩa |
| `exams/blob_storage.py` | `BlobExamStorage`: đẩy file đề lên Vercel Blob, liệt kê index, dựng URL public; từ chối đổi tên/xóa | mạng |
| `exams/router.py` | `api_router` (`/api/*`, gồm `GET /api/health`); `blob_files_router` (`/exams/*` khi hosted) | HTTP |
| `paths.py` | Vị trí thư mục; trên Vercel `EXAMS = /tmp/exams` | — |

Lối vào: `crawl.py` (gọi `cli.main`), `api/index.py` (Vercel function, import
`exam_practice.main`), `uvicorn exam_practice.main:app`.

## Luồng một request

`exams/router.py` chỉ đọc request và đổi lỗi nghiệp vụ thành HTTP status. Quy trình
nằm ở `ExamService`, còn việc ghi đĩa hay ghi Blob là của `ExamStorage`. Chuỗi gọi là
`router → ExamService → ExamStorage`.

`ExamStorage` là Strategy: `LocalExamStorage` và `BlobExamStorage` cùng một giao diện,
nên khác biệt local/hosted nằm trong object storage mà `main.create_app` chọn, không
rải `if hosted` khắp service. Hai chỗ router vẫn xét `hosted`: `PATCH`/`DELETE` trả `403`
trước khi kiểm tra tên, và `main` gắn `blob_files_router` chỉ khi hosted.

## Hai chế độ chạy

Chế độ do `main.create_app` chọn lúc khởi tạo app (`app = create_app()` khi import
`exam_practice.main`): `AppConfig.hosted` đúng khi có `BLOB_READ_WRITE_TOKEN` → hosted.

| | Local (`./dev.sh`, `--serve`) | Hosted (Vercel) |
|---|---|---|
| Cookie crawl | Chrome của máy / `cookies.txt` / ô nhập | **bắt buộc** người dùng dán `xf_user` của họ |
| Nơi lưu đề | `exams/<code>/` | ghi tạm `/tmp/exams/<code>/` → upload Blob `exams/<code>/…` → xóa tmp |
| `GET /exams/index.json` | file tĩnh | dựng từ danh sách Blob (`BlobExamStorage.index`) |
| `GET /exams/<path>` | file tĩnh | `307` sang URL public của Blob |
| Đổi tên / xóa | được | `403` (khách nào cũng xóa được của mọi người) |
| Khóa crawl | một khóa toàn cục, trùng → `409` | không khóa (mỗi request một instance) |
| `GET /api/info` | `{"hosted": false}` | `{"hosted": true}` — web dựa vào đây để ẩn nút / bắt cookie |

Web phục vụ ở hosted là CDN của Vercel (`outputDirectory: src/web`), không qua Python.

## API

| Route | Mô tả |
|---|---|
| `GET /api/health` | `{status: "ok"}` — server đang chạy |
| `GET /api/info` | `{hosted}` |
| `POST /api/crawl` | body `{url, name?, minutes?, cookie?}` → crawl + build + (hosted: publish). Lỗi: `400` URL/crawl sai, `401` thiếu/hết cookie, `409` đang bận, `500` lỗi khác |
| `PATCH /api/exams/{code}` | body `{title}` — đổi tên (local). Lỗi: `400` tên trống, `403` hosted, `404` không có đề, `409` đang bận |
| `DELETE /api/exams/{code}` | xóa đề (local). Lỗi: `403` hosted, `404` không có đề, `409` đang bận |

Khi chạy local, uvicorn chỉ nghe `127.0.0.1` (`--serve` và `dev.sh`) vì request có thể mang cookie đăng nhập.

## Nguyên tắc khi sửa

- Logic mới về đáp án → `parse.py` (thuần, test bằng chuỗi). Định dạng đầu ra → `build.py`.
  Đừng đưa mạng vào hai file này: `--rebuild` và test phụ thuộc vào điều đó.
- Thêm trường dữ liệu cho web → `build._question` rồi `uv run crawl.py --rebuild`
  (đề cũ không cần crawl lại).
- `main.create_app(configuration, crawl_exam)` nhận cấu hình và hàm crawl qua tham số, nên test truyền `AppConfig` và fake thay vì sửa biến môi trường.
- Thêm một backend lưu đề mới → triển khai `ExamStorage` (`exams/storage.py`) rồi chọn nó trong `main.create_app`.
