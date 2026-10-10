# Tài liệu maintain

Dành cho người sửa code. Cách *dùng* app xem [README gốc](../README.md); quy ước cho
agent xem [AGENTS.md](../AGENTS.md).

| Tài liệu | Nội dung |
|---|---|
| [architecture.md](architecture.md) | Bức tranh tổng: module, ranh giới I/O, hai chế độ chạy local / hosted |
| [pipeline.md](pipeline.md) | Crawl → parse → build: cách đối chiếu đáp án, evidence, định dạng `data.json` |
| [web.md](web.md) | Frontend tĩnh `src/web/`: state, màn hình, trộn đề, xáo câu, ghi chú, theme |
| [deploy.md](deploy.md) | Deploy Vercel + Blob, biến môi trường, giới hạn khi hosted |
| [maintenance.md](maintenance.md) | Test, việc hay gặp (FuOverflow đổi markup, thêm trường dữ liệu…), xử lý sự cố |

## Một phút để định hướng

```
FuOverflow thread ──crawler.py/fetch.py──▶ exams/<code>/raw/   (HTML thô + manifest + ảnh)
                                              │
                              parse.py (thuần) + build.py (thuần, đọc ảnh)
                                              ▼
                     exams/<code>/data.json · data.js · exam.json  +  exams/index.json
                                              │
             main.py + exams/router.py (FastAPI) phục vụ /exams + /api ──▶ src/web/app.js (vanilla JS)
```

- Mọi thứ gọi mạng nằm ở `fetch.py`, `crawler.py`, `exams/blob_storage.py`; HTTP vào nằm ở `exams/router.py`.
  `parse.py`/`build.py` chạy lại được trên `raw/` không cần mạng (`--rebuild`).
- Web không có build step; Vite chỉ là dev server proxy `/api` + `/exams`.
- Không có dữ liệu mẫu trong git: mọi đề là bản crawl thật, test tự sinh fixture.
