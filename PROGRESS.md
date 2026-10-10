# PROGRESS

Cập nhật: 2026-10-09

## Đã xong và đã kiểm chứng

- Cấu trúc `exam-practice`: code trong `src/exam_practice/` + `src/web/`, mỗi mã
  đề một thư mục `exams/<code>/`.
- `parse.py`: parser thread (metadata, đính kèm, phân trang, bài viết) và
  media/bình luận, trích `Câu N: A` / `1A 2B` / chọn trần, trừ trùng theo tác giả,
  chọn đáp án theo mode của tập phương án, cờ `multi`/`contested`.
- `build.py`: `build_exam` đối chiếu phiếu -> câu hỏi + đáp án; `write_exam` ghi
  `exam.json`/`data.json`/`data.js`; `write_index` quét lại `exams/index.*`;
  `report` in bảng tổng kết.
- `crawler.py` + `cli.py`: một lệnh crawl ghi raw/ảnh/manifest, chịu lỗi từng
  đính kèm, chặn khi thiếu cookie; `--rebuild`, `--list`, `--questions`.
- `src/web/`: trang chọn đề + làm bài + kết quả. **Hai chế độ**: luyện tập chấm
  ngay (đúng/sai hiện tức thì, câu nhiều đáp án có nút Kiểm tra, lưới câu tô
  xanh/đỏ) và thi thử nộp mới chấm. Hỗ trợ câu nhiều đáp án với số lượng biến
  thiên (`type`/`pick`).
- Hỗ trợ nhiều kiểu nhiều-đáp-án trong parser: `A,B`, `A B`, `A/B`, `A và B`,
  `B hoặc C`.
- Mỗi câu có trường `source` (link đúng đính kèm trong bài gốc, dạng
  `…/post-<id>#attachment-<attid>`) và `media` (trang bình luận riêng của câu),
  hiện trong lúc làm bài và trong kết quả.
- (đã xoá) `scripts/make_sample.py` từng tạo **đề mẫu tự chứa** (20 câu riêng, đáp án khớp option
  trong ảnh) và **không gắn link trace**, vì ảnh giả không tương ứng trang FUO nào.
  Link `source`/`media` chỉ có ở đề crawl thật, khi đó ảnh và link luôn khớp.
- `registry.py` + mode `--register` / `--sync`: đặt tên đề + link lưu vào
  `exams/registry.json`; `--sync` crawl đề thiếu/cũ (`--ttl-days`) để chạy cron.
- Đã kiểm chứng: `uv run pytest -q` 25 test pass; `--list` in đúng; `--sync` skip
  khi đề còn mới; `--sync --force` chặn đúng khi thiếu cookie; render headless
  Chrome (chọn đề, bắt đầu, luyện tập đúng/sai, luyện tập nhiều đáp án, kết quả,
  hai link bài gốc/bình luận); `node --check src/web/app.js`.

- **Ô crawl đề trên web (2026-10-10):** `crawl.py --serve` (`server.py`, stdlib
  `ThreadingHTTPServer`, 127.0.0.1) phục vụ web + `POST /api/crawl`; chỉ nhận link
  `https://fuoverflow.com/threads/...`, một lượt crawl một lúc (409), cookie tuỳ chọn
  từ form không được lưu; crawl xong đăng ký vào registry và mở đề. Trang chọn đề
  luôn là màn đầu (trước đây một đề thì tự mở). Đề mẫu chuyển sang mã `sample`,
  không mang link thread thật. Kiểm chứng: 30 test pass (5 test server mới);
  `--serve` thật: `/` → 302, thiếu cookies.txt → 400, cookie sai → 401; render
  headless trang chọn đề có form. Chưa kiểm chứng: crawl thành công qua form (cần
  cookie thật), luồng submit trong trình duyệt.

- **Dev stack + bỏ đề mẫu (2026-10-10):** backend chuyển sang FastAPI/uvicorn
  (`server.py`, `create_app(crawl)` để test), frontend chạy Vite :5173 (root
  `src/web/`, proxy `/api` + `/exams`), `Procfile` + `dev.sh` khởi động cả hai bằng
  honcho; `API_PORT` đổi cổng backend. Logic dùng chung tách ra
  `crawler.crawl_exam`, `registry.register`, `fetch.load_cookies`. Xoá
  `scripts/make_sample.py` và `exams/sample/`; web bỏ mọi nhánh `sample`.
  Kiểm chứng: 30 test pass; `API_PORT=8011 ./dev.sh` → Vite 200, proxy `/exams` 200,
  POST thiếu cookie 401, link lạ 400; render headless :5173 có form; Ctrl+C dừng cả
  hai; `crawl.py --serve` 200. Chưa kiểm chứng: crawl thành công (cần cookie thật).

- **Cookie tự động từ Chrome + đánh số theo tên ảnh (2026-10-10):**
  `fetch.load_cookies`: cookie dán → `cookies.txt` → Chrome (pycookiecheat; khoá
  "Chrome Safe Storage" lấy bằng `security` vì `keyring` bị Keychain từ chối, quét
  mọi profile tìm `xf_user`). `parse_attachments` đánh số câu theo tên file
  (`Q46.webp`, `Câu 12.png`) khi mọi ảnh đều có số, vì người đăng đính kèm lộn thứ
  tự; `build` lấy số câu = chỉ số lớn nhất. Kiểm chứng: crawl thật
  `hcm202-su26-re` bằng cookie Chrome: 60 câu, 59 có đáp án (Q37 không có phiếu),
  ảnh/media/số câu khớp 60/60; 31 test pass.

- **Bố cục làm bài toàn chiều ngang (2026-10-10):** ảnh đề trải hết cột chính,
  4 đáp án một hàng ngay dưới, lưới câu 1–60 (6 cột) dính góc phải; trang kết quả
  cũng rộng ra. `build.text_view` (Pillow) tính một khung chữ chung cho cả đề (bỏ
  qua logo FUO góc dưới trái) lưu vào `data.view`; web cắt ảnh theo khung đó bằng
  CSS, không sửa ảnh gốc, bấm ảnh mở ảnh đầy đủ. `hcm202-su26-re`: khung 771×282
  trên ảnh 1920×720 → chữ to ~2.5 lần. Kiểm chứng: 33 test pass; ảnh chụp headless
  1348px (luyện tập, kết quả). Còn lại: topbar tràn ngang ở màn < 520px (có từ
  trước).

- **Rà pattern + E2E web (2026-10-10):** `crawler` báo lỗi bằng `CrawlError` thay
  cho `SystemExit` (CLI và HTTP tự map ở biên của mình); bỏ các hash QA
  (`#auto/#result/#practice`) khỏi `app.js`; gộp link trace (`traceLinks`) và chấm
  điểm (`grade` dùng `isCorrect`). `tests/test_web_e2e.py`: 11 test Playwright chạy
  Chrome thật trên FastAPI + exams tạm, crawl giả — phủ kho đề, form crawl (thành
  công, link sai, cookie hết hạn), đề rỗng, màn bắt đầu, luyện tập (đúng/sai, xem
  đáp án, nhiều đáp án, không đáp án, điều hướng, nộp, ôn câu sai), thi thử + phím
  tắt + tạm dừng, hết giờ tự nộp, theme, đổi đề. Kiểm chứng: 45 test pass; thử đột
  biến (chấm luôn đúng, nút crawl không mở lại) đều bị test bắt.

- **Xóa / đổi tên đề, lọc câu (2026-10-10):** `catalog.py` (rename cập nhật
  `data.*`, `exam.json`, `raw/manifest.json`, tên trong sổ, index; delete xóa thư mục,
  mục sổ, index; mã đề kiểm theo `[a-z0-9][a-z0-9._-]*` để không thoát khỏi `exams/`).
  API `PATCH`/`DELETE /api/exams/{code}` (400 tên rỗng, 404 không có đề, 409 khi đang
  có thao tác khác — cùng khoá với crawl). Thẻ đề có Đổi tên (prompt) và Xóa (confirm).
  Trang kết quả có lọc Tất cả · Sai · Đúng. Kiểm chứng: 16 E2E + unit/API, tổng 59 test
  pass; đột biến bộ lọc bị bắt; ảnh chụp trên đề thật.

- **Bỏ honcho (2026-10-10):** honcho 2.0 trên Python 3.13 crash khi Ctrl+C
  (`RuntimeError: reentrant call` trong signal handler) và để sót Vite chiếm :5173.
  `dev.sh` giờ tự chạy `.venv/bin/uvicorn` + `node_modules/.bin/vite` nền, `trap`
  dừng cả hai; xoá `Procfile` và dependency honcho. Kiểm chứng: Ctrl+C qua pty và
  SIGTERM đều dừng sạch (0 tiến trình sót), proxy `/exams` trả 200 khi đang chạy.

- **Deploy Vercel + ghi chú mỗi câu (2026-10-10):** chế độ hosted khi có
  `BLOB_READ_WRITE_TOKEN`: `POST /api/crawl` bắt buộc cookie của người dùng (không
  rơi về cookies.txt/Chrome), crawl vào `/tmp/exams` rồi `blobstore.publish` lên
  Vercel Blob và xoá tmp; `/exams/index.json` dựng từ Blob, `/exams/*` 307 sang URL
  Blob; PATCH/DELETE → 403; không khoá toàn cục để nhiều người crawl song song.
  `api/index.py` + `vercel.json` (web tĩnh `src/web`, rewrite `/api` `/exams`,
  `maxDuration` 300), `.vercelignore`. `pycookiecheat` import lười. Web: `/api/info`
  báo hosted → ô cookie bắt buộc, ẩn Đổi tên/Xóa. Ghi chú: ô dưới mỗi câu
  (localStorage `notes:<code>`), chấm trên lưới câu, hiện ở kết quả, màn **Ghi chú**
  (sửa tại chỗ, luyện các câu có ghi chú, xuất/nhập JSON). Kiểm chứng: 66 test pass
  (5 API hosted, 2 E2E mới); ảnh chụp headless quiz + màn ghi chú trên đề thật.
  Chưa kiểm chứng: deploy thật lên Vercel, Blob thật, FuOverflow có chặn IP Vercel không.

- **Thanh tiến trình crawl + header mobile (2026-10-10):** `crawler` báo `progress(done,
  total, label)` theo trang thread/ảnh; `POST /api/crawl/stream` trả NDJSON, web vẽ thanh
  tiến trình + "Tải ảnh và bình luận 21/60 · 37%". Header làm bài trên điện thoại thành
  hai hàng, không chồng nút từ 320px. Kiểm chứng: 80 test pass (2 API + 1 E2E mới).
  Chưa kiểm chứng: stream trên Vercel và với crawl thật (cần cookie).

- **Bố cục làm bài + trộn đề xoay vòng (2026-10-10, nhánh `feat/review-hub`):** trái là ảnh
  đề trong khung cao cố định (đổi câu không giật, kiểm: vị trí đáp án giữ nguyên qua 12 câu)
  + đáp án kèm số lượt chọn sau khi chấm; phải là lưới câu, Trước/Sau, ghi chú + nút **Lưu**.
  Kết quả có nút **← Kho đề**. Trộn đề ưu tiên câu chưa gặp (`mix:seen`), 4 lượt × 20 câu
  không trùng; "Làm lại" đề trộn bốc bộ mới. Kiểm chứng: 77 test pass, ảnh chụp sáng/tối/mobile.

- **Ôn lại câu sai + ghi chú (2026-10-10, nhánh `feat/review-hub`):** section **Ôn lại**
  ở kho đề với hai thẻ "câu làm sai" / "câu có ghi chú", đếm trên mọi đề. Câu sai lưu ở
  localStorage `wrong:<code>` (ghi khi chấm/nộp, đúng lại thì tự xóa, nút "Đã nắm" xóa
  tay); mở thẻ ra danh sách kèm lựa chọn lần trước, đáp án, bình luận đối chiếu và
  **Luyện N câu này**. Kiểm chứng: 77 test pass (1 E2E mới), ảnh chụp trên đề thật.

- **Refactor backend (2026-10-10, nhánh `refactor/backend-layout`):** `server.py` +
  `blobstore.py` → `main.py` (composition root) + `app_config.py` (pydantic-settings,
  chỉ đọc biến môi trường, không `.env`) + gói `exams/` (schema, router, `ExamService`,
  strategy `ExamStorage` = `LocalExamStorage` / `BlobExamStorage`). Hành vi HTTP giữ
  nguyên (so 27 request cũ/mới khớp), thêm `GET /api/health`, log bằng `logging`,
  `--serve` tự reload. Kiểm chứng: 76 test pass; clone mới + `uv sync` chạy được không
  cần cấu hình.

- **Theme sáng/tối, trộn đề, xáo câu, evidence + docs/ (2026-10-10):** token CSS
  dùng `light-dark()` (Tự động/Sáng/Tối, nút theme luôn trên header, bỏ gradient nền);
  **Trộn đề** ở kho đề (chọn ≥ 2 đề + số câu, câu mang `code`/`orig`, đánh số lại);
  chip **Thứ tự câu: Theo đề / Xáo trộn**; `Vote.text` + `Answer.evidence` →
  `evidence` trong `data.json`, web hiện "Bình luận đối chiếu · X/Y khớp" (tự mở khi
  tranh chấp). Đề cũ đã `--rebuild`. Thêm `docs/` cho người maintain (kiến trúc,
  pipeline, web, deploy, bảo trì). Kiểm chứng: test parse evidence + 3 E2E mới;
  ảnh chụp sáng/tối kho đề, màn bắt đầu, làm bài.

## QA round (reviewer, opencode-go/glm-5.3:high)

Đã sửa theo kết quả QA:

- **P1 chấm sai câu không đáp án:** `grade`/`isCorrect`/`feedback` coi `key=[]` là
  đúng khi bỏ trống; giờ yêu cầu `key.length > 0` và hiện "chưa có đáp án". Kiểm
  chứng headless: 2 câu (1 không đáp án, bỏ trống) → 0/2.
- **P1 regex bắt nhầm số dài:** `_ENTRY_RE` thêm `(?<!\d)…(?!\d)`; "năm 2023 A",
  "mã 2705B", "attachment 147969A" không còn sinh phiếu sai.
- **P2 trùng phiếu theo tác giả:** dedup theo `(câu, tác giả)`, phiếu sau thắng
  (sửa lại đáp án thay vì cộng dồn).
- **P2 `--rebuild` bỏ phút trong registry:** đọc `registry.json` để giữ `minutes`
  theo từng mã đề. Kiểm chứng: registry 30 → rebuild ra 30.
- **P2 phím tắt chết sau khi bấm nút:** chỉ bỏ qua phím khi focus ở INPUT/TEXTAREA/
  SELECT (không bỏ qua BUTTON); Enter để nút đang focus tự xử lý.
- **P2 `parse_posts` tính cả nội dung trích dẫn:** gỡ `blockquote`/`.bbCodeQuote`
  trước khi lấy text.
- **P3 `LoginRequired` ra traceback:** bắt trong `main()` → `SystemExit` gọn.
  Kiểm chứng: cookie thiếu `xf_user` → thông báo gọn, exit 1.
- **P3 bỏ `image_votes`/`_attachment_for` không dùng:** map câu → ảnh theo index.

Còn lại (chưa làm, ghi nhận):

- Chưa có test cho `cli.py`, `crawler.py`, `fetch.py` (web đã có E2E, xem dưới).
- `--questions N` vẫn áp chung cho mọi đề khi `--rebuild`.
- Không kiểm chứng được markup thật của trang media (thiếu `raw/`).

## Chưa kiểm chứng (cần phiên đăng nhập)

- Markup thật của trang media/bình luận FuOverflow. Parser dò nhiều selector; nếu
  sai, xem `exams/<code>/raw/media-*.html`, chỉnh `parse.py`, chạy `--rebuild`.
- Số câu thật trên mỗi ảnh (giả định 1 ảnh = 1 câu; có `--questions N`).

## Tiếp theo

- Chạy `crawl.py` với cookie thật cho `hcm202-q2-6`, kiểm tra bảng tổng kết.
- Đăng ký đề mới: `crawl.py <url> --name "..." --register`; cron bằng `--sync`.
- Xác nhận "vài loại nhiều đáp án" có phải dạng Đúng/Sai theo từng mệnh đề không;
  nếu có thì thêm `type: "truefalse"` và giao diện Đ/S tương ứng.
- Cân nhắc OCR chữ từ ảnh nếu muốn hiện đề dạng text.
- Dự án cũ `~/Projects/hcm202-q2-6` là bản đầu, có thể xoá.
