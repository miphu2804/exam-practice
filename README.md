# exam-practice

Ôn luyện đề trắc nghiệm lấy từ các thread FuOverflow. Một lệnh crawl là có đề:
tải ảnh đề và bình luận, **tự đối chiếu** đáp án theo phương án được bình chọn
nhiều nhất, rồi mở web tĩnh để làm bài với thanh thời gian đặt thủ công.

Mỗi mã đề là một thư mục riêng trong `exams/`, code nằm trong `src/`. Tài liệu
cho người maintain: [docs/](docs/README.md).

## Chạy nhanh

```bash
# 1. Đăng nhập fuoverflow.com trên Chrome. Cookie được tự đọc từ Chrome
#    (lần đầu macOS có thể hỏi quyền Keychain "Chrome Safe Storage" -> Always Allow).
#    Thay thế: cookies.txt (Netscape) ở gốc dự án, hoặc --cookie 'xf_user=...'

# 2. Crawl + tự đối chiếu đáp án cho một đề
uv run crawl.py https://fuoverflow.com/threads/hcm202-q2-6.2757/

# 3. Mở giao diện: backend (uvicorn :8000) + frontend (Vite :5173) bằng một lệnh
./dev.sh
#   -> http://localhost:5173/      (Ctrl+C dừng cả hai)
```

`dev.sh` vào gốc dự án, `uv sync`, `npm install` nếu chưa có `node_modules`, rồi
chạy song song hai tiến trình (Ctrl+C dừng cả hai, không để sót tiến trình):

- backend: `uvicorn exam_practice.server:app --reload` (FastAPI, chỉ reload khi sửa
  `src/exam_practice/`, không reload khi crawl ghi vào `exams/`).
- frontend: `vite` (Vite, root `src/web/`, live reload khi sửa HTML/CSS/JS);
  Vite proxy `/api` và `/exams` sang backend.

Cổng backend đổi bằng `API_PORT=8011 ./dev.sh`. Không cần Node thì
`uv run crawl.py --serve` chạy riêng backend, nó cũng phục vụ luôn web tại
http://localhost:8000/.

Trang đầu là kho đề, có ô **"Thêm đề từ FuOverflow"**: dán link thread, bấm
**Crawl đề** là backend chạy đúng pipeline như dòng lệnh, lưu đề vào
`exams/registry.json` rồi mở đề vừa crawl. "Tuỳ chọn" cho đặt tên, số phút và dán
cookie `xf_user` (bỏ trống thì dùng `cookies.txt`, không có thì tự lấy từ Chrome;
cookie không được lưu). Backend
chỉ nghe `127.0.0.1` và chỉ nhận link `https://fuoverflow.com/threads/...`.

Mỗi thẻ đề có **Đổi tên** (đổi luôn trong sổ đăng ký và manifest, nên `--sync` /
`--rebuild` giữ tên mới) và **Xóa** (hỏi xác nhận; xóa `exams/<code>/`, mục trong sổ
và index). Ở trang kết quả, các nút **Tất cả · Sai · Đúng** lọc danh sách xem lại;
"Sai" gồm cả câu bỏ trống và câu chưa có đáp án.

Tốc độ crawl do FuOverflow quyết định (mỗi ảnh một lượt tải, nghỉ 0.6 s giữa các
request), không phụ thuộc server web.

## Chia sẻ: người khác chạy thử

Repo chỉ chứa code: ảnh đề, trang đã crawl và `exams/index.*` không được commit, nên
bản clone sạch bắt đầu từ kho đề trống. Hai lệnh cần nhớ:

```bash
# Lần đầu (cần uv + node: brew install uv node)
git clone https://github.com/miphu2804/exam-practice.git && cd exam-practice && ./dev.sh

# Các lần sau
git pull && ./dev.sh
```

`dev.sh` tự `uv sync` + `npm install`, chạy backend và Vite, rồi mở
http://localhost:5173/. Thêm đề đầu tiên ngay trên web: đăng nhập fuoverflow.com
trên Chrome, dán link thread vào ô **"Thêm đề từ FuOverflow"**, bấm **Crawl đề**
(cookie tự lấy từ Chrome và không được lưu).

## Deploy Vercel (nhiều người dùng chung, không tài khoản)

Bản deploy không có cookie của ai: mỗi người tự dán cookie `xf_user` FuOverflow của
mình khi crawl (server dùng cho đúng lượt đó, không lưu). Đề crawl xong nằm trong
Vercel Blob và ai mở trang cũng thấy; tiến độ làm bài và ghi chú lưu trong trình
duyệt từng người. Đổi tên/xóa đề bị tắt trên bản deploy (không phân quyền nên ai
cũng xóa được của người khác); làm việc đó ở bản local.

```bash
npx vercel link                       # tạo/gắn project
npx vercel blob create-store exam-practice --access public --yes   # Blob store public, gắn vào project -> BLOB_READ_WRITE_TOKEN
npx vercel deploy --prod
```

`vercel.json`: web tĩnh `src/web` qua CDN; `/api/*` và `/exams/*` vào function
`api/index.py` (FastAPI, `maxDuration` 300 s — một đề ~60 ảnh crawl mất 1–2 phút).
Có `BLOB_READ_WRITE_TOKEN` là server chạy chế độ hosted (`/api/info` → `hosted: true`).

## Ghi chú mỗi câu

Ô **Ghi chú** dưới mỗi câu, tự lưu khi gõ (localStorage, theo từng đề). Câu có ghi
chú có chấm vàng trên lưới câu và hiện ghi chú trong trang kết quả. Nút **Ghi chú ·
N** ở màn bắt đầu mở danh sách các câu đã ghi chú: sửa tại chỗ (xóa trắng = bỏ ghi
chú), **Luyện N câu này**, và **Xuất/Nhập file** để chuyển ghi chú sang máy khác.

## Chế độ làm bài

Chọn ở màn bắt đầu:

- **Luyện tập · chấm ngay:** chọn đáp án là biết đúng/sai ngay. Câu một đáp án
  chấm khi bấm; câu nhiều đáp án chọn xong bấm **Kiểm tra**; có **Xem đáp án** để
  hiện đáp án trước. Lưới câu tô xanh/đỏ theo từng câu đã chấm.
- **Thi thử · nộp mới chấm:** làm hết rồi bấm **Nộp bài** mới hiện đáp án và điểm.

Cả hai đều có thanh thời gian đặt thủ công, tạm dừng, phím tắt **A–D / 1–4**,
**← →**, **Enter** (kiểm tra / câu tiếp), **P** (tạm dừng).

Mỗi câu có hai link trace: **"↗ bài gốc"** mở đúng đính kèm trong bài viết (dạng
`…/post-5495#attachment-147969`, không phải cả thread) và **"bình luận ↗"** mở
trang media riêng của câu đó (nơi có bình chọn đáp án).

Mọi đề đều là bản crawl thật: ảnh gốc của bài viết và đáp án đối chiếu từ bình
luận gốc của người dùng, nên ảnh và hai link luôn khớp nhau.

Màn làm bài: ảnh đề trải hết chiều ngang, 4 đáp án nằm ngay dưới, lưới câu
1–N ở góc phải. Ảnh chụp đề thường trống phần lớn (chữ chỉ ở góc trên trái), nên
lúc build `data.json` có `view` là khung chứa chữ chung của cả đề; web phóng ảnh
theo khung đó (ảnh gốc giữ nguyên, bấm vào ảnh để mở bản đầy đủ). Đề cũ chưa có
`view` thì chạy `uv run crawl.py --rebuild`.

**Thứ tự câu:** *Theo đề* hoặc *Xáo trộn* (mỗi lần bắt đầu xáo lại). **Trộn đề:**
ở kho đề chọn từ 2 đề trở lên + số câu → lấy ngẫu nhiên, mỗi câu ghi rõ đề gốc.
Sau khi chấm, **Bình luận đối chiếu** liệt kê các bình luận đã bầu cho câu đó (khớp /
lệch đáp án) để tự kiểm chứng; tự mở khi câu bị tranh chấp. Nút góc phải header đổi
giao diện **Tự động / Sáng / Tối**.

Câu **nhiều đáp án** hiện thẻ "chọn N đáp án" (N lấy từ đáp án đối chiếu) và dùng
nút bật/tắt nhiều lựa chọn; số đáp án có thể là 2, 3 hoặc 4.

## Thêm đề & tự động set up (cron)

Đặt tên đề và đưa link, lưu vào sổ đăng ký:

```bash
uv run crawl.py https://fuoverflow.com/threads/<slug>/ --name "MLN111 FE" --register
```

`--register` ghi vào `exams/registry.json` (code lấy từ slug URL, đổi bằng `--code`,
thời gian bằng `--minutes`). Sổ này sửa tay được:

```json
[{ "code": "mln111-fe", "name": "MLN111 FE", "url": "https://...", "minutes": 45 }]
```

**Cron:** `--sync` đọc sổ, crawl đề còn thiếu hoặc cũ hơn `--ttl-days` (mặc định 7),
rồi cập nhật index. Thêm `--force` để luôn crawl lại, `--only CODE` để giới hạn.

```bash
# 3h sáng mỗi ngày: tự set up / làm mới mọi đề đã đăng ký
0 3 * * * cd ~/Projects/exam-practice && uv run crawl.py --sync >> .sync.log 2>&1
```

Cookie phải còn hạn (`cookies.txt` ở gốc dự án).

## Tự đối chiếu đáp án

Mỗi ảnh đính kèm là một trang đề. Crawler lấy bình luận của từng ảnh và đối chiếu:

- `Câu 12: A`, `1A 2B` được tính cho đúng số câu ghi trong bình luận.
- Bình luận ngắn `A`, `A,B`, "mình chọn A" được tính cho câu của trang đó.
- Mỗi tác giả chỉ tính một lần cho mỗi câu.
- **Đáp án = tập phương án xuất hiện nhiều nhất.** Tập có ≥2 phương án → cờ
  `nhiều đáp án`; phương án bám đuổi trong 25% → cờ `tranh chấp`.

Sau khi crawl, CLI in bảng tổng kết (`key`, số bình chọn, cờ, phân bố) để bạn tự
kiểm chứng. Phân tích lại không cần mạng:

```bash
uv run crawl.py --rebuild            # tất cả đề
uv run crawl.py --rebuild hcm202-q2-6
uv run crawl.py --list
```

## Cấu trúc

```
crawl.py                       lệnh tiện dụng -> exam_practice.cli
src/exam_practice/
  cli.py                       tham số dòng lệnh + mode (crawl/register/sync/rebuild/serve)
  server.py                    FastAPI: crawl, đổi tên, xóa đề + phục vụ exams/ và web
  catalog.py                   đổi tên / xóa đề (thư mục, manifest, sổ, index)
  crawler.py                   tải thread + media + ảnh vào exams/<code>/
  registry.py                  đọc/ghi exams/registry.json
  fetch.py                     phiên HTTP, cookie, tải file
  parse.py                     parser thuần HTML -> dữ liệu (không I/O)
  build.py                     raw -> data.json/data.js + index + báo cáo
  paths.py                     vị trí thư mục
src/web/                       giao diện tĩnh: index.html, styles.css, app.js
exams/
  registry.json                sổ đề đăng ký (sửa tay hoặc --register)
  index.json, index.js         danh sách đề (sinh tự động)
  <code>/
    exam.json                  tóm tắt
    data.json, data.js         câu hỏi + đáp án
    images/                    ảnh trang đề
    raw/                       HTML thô + manifest (chạy lại được)
dev.sh                         chạy backend + frontend cùng lúc
package.json, vite.config.js   dev server Vite cho src/web/ (:5173)
tests/                         test parser, pipeline, API + E2E web (test_web_e2e.py)
```

`exams/<code>/raw/` và `exams/<code>/images/` không commit (tải lại được).

## Định dạng dữ liệu

`exams/<code>/data.json` (và `data.js` với biến `window.EXAM_DATA`):

```json
{
  "code": "hcm202-q2-6",
  "title": "Đề Thi PT - HCM202 - Q2 - 6",
  "source": "https://fuoverflow.com/threads/hcm202-q2-6.2757/",
  "default_duration_min": 45,
  "choices": ["A", "B", "C", "D"],
  "stats": { "questions": 20, "answered": 20, "contested": 4, "multi": 3, "votes": 150 },
  "questions": [
    {
      "n": 1,
      "image": "images/q01.webp",
      "source": "https://fuoverflow.com/threads/hcm202-q2-6.2757/post-5495#attachment-147969",
      "media": "https://fuoverflow.com/media/hcm202_-_q2_-_6_2757-webp.70478/",
      "type": "single",
      "answer": ["A"],
      "multi": false,
      "pick": 1,
      "contested": false,
      "letter_votes": { "A": 4, "B": 1, "C": 2, "D": 0 },
      "vote_count": 7,
      "evidence": [{ "author": "an", "letters": ["A"], "text": "Câu 1: A" }]
    }
  ]
}
```

## Giới hạn

- Nội dung câu hỏi và phương án nằm trong ảnh; giao diện hiển thị ảnh và bốn nút
  A/B/C/D, chưa OCR thành chữ.
- Giả định 1 ảnh = 1 câu; dùng `--questions N` nếu một ảnh chứa nhiều câu.
- Đáp án suy từ bình luận nên có thể sai khi ít/nhiễu; phần kết quả hiện phân bố
  bình chọn và cờ tranh chấp để tự kiểm chứng. Câu chưa đủ dữ liệu (không có đáp án)
  hiện "chưa có đáp án" và không được tính đúng.
- Parser dò nhiều selector của XenForo Media Gallery; nếu FuOverflow đổi markup,
  xem `exams/<code>/raw/media-*.html`, chỉnh `src/exam_practice/parse.py` rồi
  `uv run crawl.py --rebuild`.
