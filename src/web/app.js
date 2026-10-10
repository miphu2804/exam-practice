(() => {
  "use strict";

  const EXAMS = "../../exams/";
  const $ = (sel, root = document) => root.querySelector(sel);
  const esc = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const img = (path) => (path ? EXAMS + state.code + "/" + path : "");
  const fmt = (letters) => {
    const list = [...(letters || [])].sort();
    return list.length ? list.join(", ") : "";
  };

  const state = {
    index: [],
    code: "",
    data: null,
    mode: "practice",
    queue: [],
    i: 0,
    answers: new Map(),
    checked: new Set(),
    painted: null,
    durationMs: 0,
    remainingMs: 0,
    endsAt: 0,
    timer: null,
    running: false,
    finished: false,
  };

  const question = (n) => state.data.questions.find((q) => q.n === n);
  const chosen = (n) => state.answers.get(n) || new Set();
  const keyOf = (q) => q.answer || [];
  const sameSet = (a, b) => a.size === b.length && [...a].every((c) => b.includes(c));
  const isCorrect = (n) => {
    const key = keyOf(question(n));
    return key.length > 0 && sameSet(chosen(n), key);
  };
  const revealed = (n) => state.mode === "practice" && state.checked.has(n);

  /* --------------------------------------------------------------- notes */
  // Notes stay in this browser only (one key per exam), so every user keeps their own.
  const NOTES = "notes:";
  function notesOf(code = state.code) {
    try {
      return JSON.parse(localStorage.getItem(NOTES + code)) || {};
    } catch {
      return {};
    }
  }
  const noteOf = (n) => notesOf()[n] || "";
  const notedQuestions = () => {
    const notes = notesOf();
    return state.data.questions.map((q) => q.n).filter((n) => notes[n]);
  };
  function saveNote(n, text) {
    const notes = notesOf();
    if (text.trim()) notes[n] = text;
    else delete notes[n];
    try {
      localStorage.setItem(NOTES + state.code, JSON.stringify(notes));
    } catch {
      /* storage full or blocked: the note lives until the page closes */
    }
  }

  /* ------------------------------------------------------------- loading */
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = src;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error(src));
      document.head.appendChild(script);
    });
  }

  async function loadJson(path, key) {
    const fresh = "?t=" + Date.now(); // a crawl rewrites these files while the page is open
    delete window[key];
    try {
      await loadScript(path + fresh);
    } catch {
      /* fall through to fetch */
    }
    if (window[key]) return window[key];
    try {
      const response = await fetch(path.replace(/\.js$/, ".json") + fresh);
      return response.ok ? await response.json() : null;
    } catch {
      return null;
    }
  }

  async function boot() {
    document.documentElement.dataset.theme = localStorage.getItem("theme") || "";
    bindChrome();
    state.hosted = await fetch("/api/info")
      .then((response) => (response.ok ? response.json() : {}))
      .then((info) => Boolean(info.hosted))
      .catch(() => false);
    await loadIndex();
    renderPicker();
  }

  async function loadIndex() {
    state.index = (await loadJson(EXAMS + "index.js", "EXAM_INDEX")) || [];
  }

  async function openExam(entry) {
    state.code = entry.code;
    const data = await loadJson(EXAMS + entry.code + "/data.js", "EXAM_DATA");
    if (!data || !Array.isArray(data.questions) || !data.questions.length) return renderEmpty(entry);
    state.data = data;
    document.title = `${data.code} · Luyện đề`;
    $("#brand").innerHTML = `<b>${esc(data.code)}</b>`;
    $("#foot-meta").textContent = `${data.code}${data.generated ? " · " + data.generated.slice(0, 10) : ""}`;
    $("#switch").hidden = false;
    renderStart();
  }

  function bindChrome() {
    $("#theme").addEventListener("click", cycleTheme);
    $("#pause").addEventListener("click", togglePause);
    $("#submit").addEventListener("click", () => finish());
    $("#switch").addEventListener("click", () => {
      stopTimer();
      state.data = null;
      renderPicker();
    });
  }

  function cycleTheme() {
    const order = ["", "light", "dark"];
    const next = order[(order.indexOf(localStorage.getItem("theme") || "") + 1) % order.length];
    localStorage.setItem("theme", next);
    document.documentElement.dataset.theme = next;
  }

  /* -------------------------------------------------------------- picker */
  function renderPicker() {
    $("#topbar").hidden = true;
    $("#brand").innerHTML = "<b>exam-practice</b>";
    $("#foot-meta").textContent = "";
    $("#app").innerHTML = `
      <section class="screen-enter">
        <span class="eyebrow">Kho đề</span>
        <h1 class="picker-title">${state.index.length ? "Chọn đề để làm" : "Chưa có đề nào"}</h1>
        ${crawlForm()}
        <p class="picker-status" id="picker-status" role="status"></p>
        <div class="exam-grid">${state.index.map(examCard).join("")}</div>
      </section>`;
    document.querySelectorAll(".exam-card").forEach((card, i) => {
      const entry = state.index[i];
      card.querySelector(".exam-main").addEventListener("click", () => openExam(entry));
      card.querySelector("[data-act=rename]")?.addEventListener("click", () => renameExam(entry));
      card.querySelector("[data-act=delete]")?.addEventListener("click", () => deleteExam(entry));
    });
    $("#crawl").addEventListener("submit", submitCrawl);
  }

  async function renameExam(entry) {
    const current = entry.title || entry.code;
    const title = prompt(`Tên mới cho đề ${entry.code}:`, current)?.trim();
    if (!title || title === current) return;
    await changeExam(entry, "PATCH", { title });
  }

  async function deleteExam(entry) {
    const ok = confirm(`Xóa đề "${entry.title || entry.code}"?\nẢnh, dữ liệu đã crawl và mục trong sổ đăng ký sẽ bị xóa; muốn có lại phải crawl lại.`);
    if (ok) await changeExam(entry, "DELETE");
  }

  /** Send a rename/delete to the backend, then redraw the picker from the fresh index. */
  async function changeExam(entry, method, body) {
    const status = $("#picker-status");
    try {
      const response = await fetch(`/api/exams/${encodeURIComponent(entry.code)}`, {
        method,
        headers: body ? { "Content-Type": "application/json" } : {},
        body: body ? JSON.stringify(body) : undefined,
      });
      const result = await response.json().catch(() => null);
      if (!response.ok || !result) {
        throw new Error(typeof result?.detail === "string" ? result.detail : backendUnavailable(response.status));
      }
    } catch (error) {
      status.textContent = error instanceof TypeError ? backendUnavailable() : error.message;
      return;
    }
    await loadIndex();
    renderPicker();
  }

  function crawlForm() {
    // Hosted: the server has no login of its own, so each user crawls with their own cookie.
    const cookie = state.hosted
      ? `<div class="crawl-row">
          <input name="cookie" type="password" autocomplete="off" required placeholder="Cookie xf_user FuOverflow của bạn" aria-label="Cookie xf_user" />
        </div>
        <p class="crawl-hint">Lấy cookie: đăng nhập fuoverflow.com → DevTools (F12) → Application → Cookies → copy giá trị <code>xf_user</code>. Cookie chỉ dùng cho lượt crawl này, không được lưu.</p>`
      : "";
    const localCookie = state.hosted
      ? ""
      : `<div class="crawl-row">
            <input name="cookie" type="password" autocomplete="off" placeholder="Cookie xf_user (bỏ trống: tự lấy từ Chrome)" aria-label="Cookie xf_user" />
          </div>`;
    return `
      <form class="crawl" id="crawl">
        <div class="crawl-head">
          <b>Thêm đề từ FuOverflow</b>
          <span>Dán link thread; crawler tải ảnh đề, bình luận và tự đối chiếu đáp án.</span>
        </div>
        <div class="crawl-row">
          <input name="url" type="url" required placeholder="https://fuoverflow.com/threads/hcm202-q2-6.2757/" aria-label="Link thread FuOverflow" />
          <button class="btn primary" type="submit">Crawl đề</button>
        </div>
        ${cookie}
        <details>
          <summary>Tuỳ chọn</summary>
          <div class="crawl-row">
            <input name="name" placeholder="Tên đề (tuỳ chọn)" aria-label="Tên đề" />
            <input name="minutes" type="number" min="1" max="240" placeholder="Phút" aria-label="Thời gian (phút)" />
          </div>
          ${localCookie}
        </details>
        <p class="crawl-status" id="crawl-status" role="status"></p>
      </form>`;
  }

  async function submitCrawl(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const status = $("#crawl-status");
    const button = form.querySelector("button[type=submit]");
    const field = (name) => form.elements[name].value.trim();
    const body = {
      url: field("url"),
      name: field("name"),
      minutes: parseInt(field("minutes"), 10) || null,
      cookie: field("cookie"),
    };
    button.disabled = true;
    status.dataset.tone = "";
    status.textContent = "Đang crawl… mỗi ảnh một lượt tải, có thể mất 1–2 phút.";
    try {
      const response = await fetch("/api/crawl", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const result = await response.json().catch(() => null);
      if (!response.ok || !result) {
        throw new Error(typeof result?.detail === "string" ? result.detail : backendUnavailable(response.status));
      }
      await loadIndex();
      const entry = state.index.find((e) => e.code === result.code);
      if (entry) return openExam(entry);
      renderPicker();
    } catch (error) {
      status.dataset.tone = "bad";
      status.textContent = error instanceof TypeError ? backendUnavailable() : error.message;
      button.disabled = false;
    }
  }

  function backendUnavailable(status) {
    return `Không gọi được backend${status ? ` (HTTP ${status})` : ""}. Chạy ./dev.sh (hoặc uv run crawl.py --serve) để bật backend.`;
  }

  function examCard(entry) {
    const s = entry.stats || {};
    const flags = [];
    if (s.contested) flags.push(`${s.contested} tranh chấp`);
    if (s.multi) flags.push(`${s.multi} nhiều đáp án`);
    return `
      <article class="exam-card">
        <button class="exam-main">
          <span class="eyebrow">${esc(entry.code)}</span>
          <h3>${esc(entry.title || entry.code)}</h3>
          <span class="exam-stats">
            <b>${s.answered ?? "?"}/${s.questions ?? "?"}</b> câu có đáp án
            ${flags.length ? `<em>${esc(flags.join(" · "))}</em>` : ""}
          </span>
          <span class="exam-open">Làm bài →</span>
        </button>
        ${state.hosted ? "" : `<div class="exam-actions">
          <button class="link-btn" data-act="rename">Đổi tên</button>
          <button class="link-btn danger" data-act="delete">Xóa</button>
        </div>`}
      </article>`;
  }

  function renderEmpty(entry) {
    $("#topbar").hidden = true;
    $("#app").innerHTML = `
      <div class="empty screen-enter">
        <p class="eyebrow">Chưa có dữ liệu</p>
        <h2>Đề <code>${esc(entry.code)}</code> chưa có câu hỏi</h2>
        <p>Crawl lại đề này từ ô "Thêm đề" ở trang chọn đề.</p>
        <button class="btn ghost" id="back">← Đổi đề</button>
      </div>`;
    $("#back").addEventListener("click", renderPicker);
  }

  /* --------------------------------------------------------------- start */
  function renderStart() {
    stopTimer();
    state.finished = false;
    state.painted = null;
    $("#topbar").hidden = true;
    const d = state.data;
    const total = d.questions.length;
    const answered = d.stats?.answered ?? d.questions.filter((q) => keyOf(q).length).length;
    const multi = d.stats?.multi ?? d.questions.filter((q) => q.multi).length;
    const minutes = d.default_duration_min || 45;
    $("#app").innerHTML = `
      <section class="start screen-enter">
        <span class="eyebrow">FuOverflow · ${esc(d.code)}</span>
        <h1>${esc(d.title || d.code)}</h1>
        <p class="lede">${total} câu hỏi, ${multi} câu nhiều đáp án. Đáp án được đối chiếu theo phương án được bình chọn nhiều nhất.</p>
        ${d.source ? `<p class="source">nguồn · <a href="${esc(d.source)}" target="_blank" rel="noopener">${esc(d.source)}</a></p>` : ""}
        <div class="meta-cards">
          <div><b>${total}</b><span>câu hỏi</span></div>
          <div><b>${answered}</b><span>câu có đáp án</span></div>
          <div><b>${d.stats?.votes ?? "—"}</b><span>lượt bình chọn</span></div>
        </div>
        <div class="setup">
          <div class="setup-row">
            <label>Chế độ</label>
            <div class="presets" role="group" aria-label="Chế độ làm bài">
              <button class="chip mode" data-mode="practice" aria-pressed="${state.mode === "practice"}">Luyện tập · chấm ngay</button>
              <button class="chip mode" data-mode="exam" aria-pressed="${state.mode === "exam"}">Thi thử · nộp mới chấm</button>
            </div>
          </div>
          <div class="setup-row">
            <label for="minutes">Thời gian (phút)</label>
            <input id="minutes" type="number" min="1" max="240" step="1" value="${minutes}" />
            <div class="presets" role="group" aria-label="Chọn nhanh">
              ${[15, 30, 45, 60, 90].map((m) => `<button class="chip" data-min="${m}">${m}</button>`).join("")}
            </div>
          </div>
        </div>
        <div class="actions">
          <button class="btn primary" id="start">Bắt đầu làm bài</button>
          <button class="btn" id="notes">Ghi chú · ${notedQuestions().length}</button>
          <button class="btn ghost" id="back">← Đổi đề</button>
        </div>
        <div class="assumption" id="mode-note"></div>
      </section>`;
    $("#notes").addEventListener("click", renderNotes);
    document.querySelectorAll(".chip[data-min]").forEach((chip) =>
      chip.addEventListener("click", () => { $("#minutes").value = chip.dataset.min; })
    );
    document.querySelectorAll(".chip.mode").forEach((chip) =>
      chip.addEventListener("click", () => {
        state.mode = chip.dataset.mode;
        document.querySelectorAll(".chip.mode").forEach((c) =>
          c.setAttribute("aria-pressed", String(c.dataset.mode === state.mode))
        );
        paintModeNote();
      })
    );
    paintModeNote();
    $("#start").addEventListener("click", () => {
      const value = Math.min(240, Math.max(1, parseInt($("#minutes").value, 10) || 45));
      start(value, d.questions.map((q) => q.n), state.mode);
    });
    $("#back").addEventListener("click", () => { state.data = null; renderPicker(); });
  }

  /* --------------------------------------------------------- notes screen */
  /** Every question of this exam that has a note, editable in place, with a drill over just those. */
  function renderNotes() {
    $("#topbar").hidden = true;
    const noted = notedQuestions();
    const notes = notesOf();
    $("#app").innerHTML = `
      <section class="screen-enter">
        <div class="result-head">
          <div>
            <p class="eyebrow">Ghi chú · ${esc(state.data.code)}</p>
            <h1 class="picker-title">${noted.length ? `${noted.length} câu có ghi chú` : "Chưa có ghi chú nào"}</h1>
          </div>
          <div class="actions" style="margin:0">
            <button class="btn" id="drill-notes" ${noted.length ? "" : "disabled"}>Luyện ${noted.length} câu này</button>
            <button class="btn ghost" id="back">← Quay lại</button>
          </div>
        </div>
        <p class="notes-transfer">
          Chuyển ghi chú (mọi đề) sang máy khác:
          <button class="link-btn" id="export-notes">Xuất file</button> ·
          <label class="link-btn">Nhập file<input type="file" id="import-notes" accept="application/json,.json" hidden /></label>
        </p>
        ${noted.length ? "" : `<p class="review-none">Ghi chú được viết ngay dưới mỗi câu khi làm bài và chỉ lưu trên trình duyệt này.</p>`}
        <div class="review">${noted.map((n) => noteItem(question(n), notes[n])).join("")}</div>
      </section>`;
    document.querySelectorAll(".note-item textarea").forEach((area) =>
      area.addEventListener("input", () => saveNote(Number(area.dataset.n), area.value))
    );
    $("#drill-notes").addEventListener("click", () => {
      const minutes = Math.max(1, Math.ceil(notedQuestions().length * 1.5));
      start(minutes, notedQuestions(), state.mode);
    });
    $("#back").addEventListener("click", renderStart);
    $("#export-notes").addEventListener("click", exportNotes);
    $("#import-notes").addEventListener("change", (event) => importNotes(event.target.files[0]));
    window.scrollTo(0, 0);
  }

  /** Download every exam's notes as ``{code: {n: text}}``. */
  function exportNotes() {
    const all = {};
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key.startsWith(NOTES)) all[key.slice(NOTES.length)] = notesOf(key.slice(NOTES.length));
    }
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([JSON.stringify(all, null, 2)], { type: "application/json" }));
    link.download = "exam-notes.json";
    link.click();
    URL.revokeObjectURL(link.href);
  }

  /** Merge an exported file into this browser; an imported note replaces the local one for the same question. */
  async function importNotes(file) {
    if (!file) return;
    try {
      const all = JSON.parse(await file.text());
      for (const [code, notes] of Object.entries(all)) {
        if (notes && typeof notes === "object") {
          localStorage.setItem(NOTES + code, JSON.stringify({ ...notesOf(code), ...notes }));
        }
      }
    } catch {
      alert("File ghi chú không hợp lệ.");
      return;
    }
    renderNotes();
  }

  function noteItem(q, text) {
    return `
      <article class="review-item note-item">
        <div>${q.image ? shot(q, "lazy") : ""}</div>
        <div>
          <div class="qhead" style="margin-bottom:8px">
            <span class="qnum">Câu ${q.n}</span>
            <span class="review-links">${traceLinks(q)}</span>
          </div>
          <div class="mini-choices">
            <span class="mini key">đáp án: ${esc(fmt(keyOf(q)) || "chưa có")}</span>
          </div>
          <textarea class="note-input" data-n="${q.n}" rows="4" aria-label="Ghi chú câu ${q.n}">${esc(text)}</textarea>
        </div>
      </article>`;
  }

  function paintModeNote() {
    const note = $("#mode-note");
    if (!note) return;
    note.textContent =
      state.mode === "practice"
        ? "Luyện tập: chọn là biết đúng/sai ngay, câu nhiều đáp án bấm Kiểm tra sau khi chọn xong."
        : "Thi thử: làm hết rồi nộp bài mới chấm điểm.";
  }

  function start(minutes, queue, mode) {
    state.mode = mode || state.mode;
    state.queue = queue;
    state.i = 0;
    state.answers = new Map();
    state.checked = new Set();
    state.painted = null;
    state.finished = false;
    state.durationMs = minutes * 60000;
    state.remainingMs = state.durationMs;
    $("#topbar").hidden = false;
    renderQuiz();
    startTimer();
  }

  /* ----------------------------------------------------------------- quiz */
  function renderQuiz() {
    $("#app").innerHTML = `
      <section class="quiz screen-enter">
        <div class="quiz-main">
          <div class="qhead"><span class="qnum" id="qnum"></span><span id="qtag"></span></div>
          <div class="image-pane" id="image-pane"></div>
          <div class="choices" id="choices" role="group" aria-label="Chọn đáp án"></div>
          <div id="feedback"></div>
          <div class="qactions" id="actions"></div>
          <textarea class="note-input" id="note" rows="2" placeholder="Ghi chú cho câu này (chỉ lưu trên trình duyệt của bạn)" aria-label="Ghi chú"></textarea>
          <div class="qnav">
            <button class="btn ghost" id="prev">← Trước</button>
            <span class="spacer"></span>
            <button class="btn" id="next">Sau →</button>
          </div>
        </div>
        <aside class="quiz-side">
          <p class="eyebrow">Câu hỏi</p>
          <div class="dots" id="dots" aria-label="Danh sách câu"></div>
        </aside>
      </section>`;
    $("#prev").addEventListener("click", () => goto(state.i - 1));
    $("#next").addEventListener("click", () => (state.i === state.queue.length - 1 ? finish() : goto(state.i + 1)));
    $("#note").addEventListener("input", (event) => {
      saveNote(state.queue[state.i], event.target.value);
      paintDots();
    });
    paint();
  }

  function paint() {
    const n = state.queue[state.i];
    const q = question(n);
    const shown = revealed(n);
    const picked = chosen(n);

    $("#counter").innerHTML = `<b>${String(state.i + 1).padStart(2, "0")}</b> / ${state.queue.length}`;
    $("#qnum").textContent = `Câu ${n}`;
    $("#qtag").innerHTML = q.multi ? `<span class="tag">${q.pick ? `chọn ${q.pick} đáp án` : "nhiều đáp án"}</span>` : "";

    if (state.painted !== n) {
      state.painted = n;
      const pane = $("#image-pane");
      const links = traceLinks(q);
      const trace = links ? `<div class="trace-row">${links}</div>` : "";
      if (q.image) {
        pane.classList.remove("missing");
        pane.innerHTML = `${shot(q)}${trace}`;
        pane.classList.remove("q-enter");
        void pane.offsetWidth;
        pane.classList.add("q-enter");
      } else {
        pane.classList.add("missing");
        pane.innerHTML = trace;
      }
      $("#note").value = noteOf(n);
    }

    const letters = q.choices?.length ? q.choices : ["A", "B", "C", "D"];
    const key = keyOf(q);
    $("#choices").innerHTML = letters
      .map((c) => {
        const mark = shown ? (key.includes(c) ? "correct" : picked.has(c) ? "wrong" : "") : "";
        return `<button class="choice" data-c="${c}" aria-pressed="${picked.has(c)}" data-state="${mark}" ${shown ? "disabled" : ""}>
             <span class="key">${c}</span>
           </button>`;
      })
      .join("");
    $("#choices").querySelectorAll(".choice").forEach((b) => b.addEventListener("click", () => select(b.dataset.c)));

    const practice = state.mode === "practice";
    $("#feedback").innerHTML = shown ? feedback(q, picked) : "";
    $("#actions").innerHTML =
      practice && !shown
        ? `${q.multi ? `<button class="btn" id="check" ${picked.size ? "" : "disabled"}>Kiểm tra</button>` : ""}
           <button class="btn ghost" id="reveal">Xem đáp án</button>`
        : "";
    const check = $("#check");
    if (check) check.addEventListener("click", checkAnswer);
    const reveal = $("#reveal");
    if (reveal) reveal.addEventListener("click", () => { state.checked.add(n); paint(); });

    $("#prev").disabled = state.i === 0;
    $("#next").textContent = state.i === state.queue.length - 1 ? "Nộp bài" : shown ? "Câu tiếp →" : "Sau →";
    paintDots();
    paintClock();
  }

  /** Question image zoomed to the exam's text box (``data.view``); click opens the full image. */
  function shot(q, loading = "eager") {
    const v = state.data.view;
    const src = esc(img(q.image));
    const style = v
      ? `width:${(v.width / v.w) * 100}%;left:${(-v.x / v.w) * 100}%;top:${(-v.y / v.h) * 100}%`
      : "";
    return `<a class="shot ${v ? "cropped" : ""}" href="${src}" target="_blank" rel="noopener" title="Mở ảnh gốc"
        ${v ? `style="aspect-ratio:${v.w}/${v.h}"` : ""}>
        <img src="${src}" alt="Câu ${q.n}" loading="${loading}" style="${style}" /></a>`;
  }

  /** Links back to the question's attachment in the post and to its comment page. */
  function traceLinks(q) {
    return [
      q.source ? `<a class="trace" href="${esc(q.source)}" target="_blank" rel="noopener">↗ bài gốc</a>` : "",
      q.media ? `<a class="trace" href="${esc(q.media)}" target="_blank" rel="noopener">bình luận ↗</a>` : "",
    ].join("");
  }

  function feedback(q, picked) {
    const key = keyOf(q);
    const hasKey = key.length > 0;
    const ok = hasKey && sameSet(picked, key);
    const yours = fmt(picked) || "chưa chọn";
    const verdict = !hasKey ? "Chưa có đáp án" : ok ? "Đúng" : "Sai";
    return `
      <div class="feedback ${!hasKey ? "muted" : ok ? "ok" : "no"}">
        <div class="fb-head">
          <span class="verdict">${verdict}</span>
          <span class="mini you">bạn: ${esc(yours)}</span>
          <span class="mini key">đáp án: ${esc(fmt(key) || "chưa có")}</span>
        </div>
        ${voteBars(q)}
      </div>`;
  }

  function voteBars(q) {
    const key = keyOf(q);
    const max = Math.max(1, ...Object.values(q.letter_votes || { _: 0 }));
    return `<div class="vote-bars">${(q.choices?.length ? q.choices : ["A", "B", "C", "D"])
      .map((c) => {
        const count = q.letter_votes?.[c] || 0;
        return `<div class="vote-row ${key.includes(c) ? "is-answer" : ""}">
            <span>${c}</span>
            <span class="vote-track"><i style="width:${(count / max) * 100}%"></i></span>
            <span>${count}</span>
          </div>`;
      })
      .join("")}</div>`;
  }

  function paintDots() {
    const box = $("#dots");
    if (!box) return;
    const notes = notesOf();
    box.innerHTML = state.queue
      .map((n, idx) => {
        const done = chosen(n).size > 0;
        const shown = revealed(n);
        const ok = shown ? isCorrect(n) : "";
        return `<button class="dot" data-idx="${idx}" data-done="${done}" data-current="${idx === state.i}"
             data-checked="${shown}" data-ok="${ok}" data-note="${Boolean(notes[n])}">${n}</button>`;
      })
      .join("");
    box.querySelectorAll(".dot").forEach((b) => b.addEventListener("click", () => goto(Number(b.dataset.idx))));
  }

  function select(letter) {
    const n = state.queue[state.i];
    const q = question(n);
    if (revealed(n)) return;
    let picked = new Set(chosen(n));
    if (q.multi) {
      picked.has(letter) ? picked.delete(letter) : picked.add(letter);
    } else {
      picked = picked.has(letter) && picked.size === 1 ? new Set() : new Set([letter]);
    }
    state.answers.set(n, picked);
    if (state.mode === "practice" && !q.multi && picked.size) state.checked.add(n);
    paint();
  }

  function checkAnswer() {
    const n = state.queue[state.i];
    if (!chosen(n).size) return;
    state.checked.add(n);
    paint();
  }

  function goto(index) {
    if (index < 0 || index >= state.queue.length) return;
    state.i = index;
    paint();
  }

  /* ---------------------------------------------------------------- timer */
  function startTimer() {
    stopTimer();
    state.endsAt = Date.now() + state.remainingMs;
    state.running = true;
    state.timer = setInterval(tick, 250);
    paintClock();
  }

  function stopTimer() {
    if (state.timer) clearInterval(state.timer);
    state.timer = null;
    state.running = false;
  }

  function togglePause() {
    if (state.running) {
      state.remainingMs = Math.max(0, state.endsAt - Date.now());
      stopTimer();
    } else {
      startTimer();
    }
    paintClock();
  }

  function tick() {
    if (!state.running) return;
    state.remainingMs = Math.max(0, state.endsAt - Date.now());
    paintClock();
    if (state.remainingMs <= 0) finish(true);
  }

  function paintClock() {
    const clock = $("#clock");
    const bar = $("#timebar");
    if (!clock || !bar) return;
    const seconds = Math.ceil(state.remainingMs / 1000);
    clock.textContent = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
    const frac = state.durationMs ? state.remainingMs / state.durationMs : 0;
    const warn = frac <= 0.25 && frac > 0.1;
    const low = frac <= 0.1;
    clock.classList.toggle("warn", warn);
    clock.classList.toggle("low", low);
    bar.querySelector("i").style.width = `${Math.max(0, Math.min(1, frac)) * 100}%`;
    bar.classList.toggle("warn", warn);
    bar.classList.toggle("low", low);
    const pause = $("#pause");
    if (pause) pause.textContent = state.running ? "Tạm dừng" : "Tiếp tục";
  }

  /* --------------------------------------------------------------- finish */
  function finish(auto = false) {
    if (state.finished) return;
    state.finished = true;
    stopTimer();
    renderResult(auto);
  }

  function grade() {
    return state.queue.map((n) => {
      const q = question(n);
      return { q, you: [...chosen(n)].sort(), key: [...keyOf(q)].sort(), ok: isCorrect(n) };
    });
  }

  function renderResult(auto) {
    $("#topbar").hidden = true;
    const items = grade();
    const correct = items.filter((x) => x.ok).length;
    const total = items.length;
    const pct = total ? Math.round((correct / total) * 100) : 0;
    const wrong = items.filter((x) => !x.ok).map((x) => x.q.n);
    const filters = [
      ["all", "Tất cả", total],
      ["wrong", "Sai", wrong.length],
      ["right", "Đúng", correct],
    ];

    $("#app").innerHTML = `
      <section class="screen-enter">
        <div class="result-head">
          <div>
            <p class="eyebrow">${auto ? "Hết giờ" : "Kết quả"} · ${esc(state.data.code)} · ${state.mode === "practice" ? "luyện tập" : "thi thử"}</p>
            <div class="score"><b>${correct}</b><span>/ ${total} câu đúng · ${pct}%</span></div>
          </div>
          <div class="actions" style="margin:0">
            <button class="btn" id="retry-wrong" ${wrong.length ? "" : "disabled"}>Ôn ${wrong.length} câu sai</button>
            <button class="btn primary" id="again">Làm lại</button>
          </div>
        </div>
        <div class="presets review-filter" role="group" aria-label="Lọc câu">
          ${filters.map(([key, label, count]) => `<button class="chip" data-filter="${key}" aria-pressed="${key === "all"}">${label} · ${count}</button>`).join("")}
        </div>
        <div class="review">${items.map(reviewItem).join("")}</div>
        <p class="review-none" id="review-none" hidden>Không có câu nào.</p>
      </section>`;
    document.querySelectorAll(".review-filter .chip").forEach((chip) =>
      chip.addEventListener("click", () => filterReview(chip.dataset.filter))
    );

    $("#again").addEventListener("click", renderStart);
    $("#retry-wrong").addEventListener("click", () => {
      wrong.forEach((n) => state.answers.delete(n));
      start(Math.max(1, Math.ceil(wrong.length * 1.5)), wrong, state.mode);
    });
    window.scrollTo(0, 0);
  }

  /** Show all reviewed questions, only the wrong ones (incl. unanswered/no key), or only the right ones. */
  function filterReview(filter) {
    document.querySelectorAll(".review-filter .chip").forEach((chip) =>
      chip.setAttribute("aria-pressed", String(chip.dataset.filter === filter))
    );
    let shown = 0;
    document.querySelectorAll(".review-item").forEach((item) => {
      const ok = item.dataset.ok === "true";
      item.hidden = filter === "wrong" ? ok : filter === "right" ? !ok : false;
      shown += item.hidden ? 0 : 1;
    });
    $("#review-none").hidden = shown > 0;
  }

  function reviewItem({ q, you, key, ok }) {
    const yours = you.join(", ") || "chưa chọn";
    const answer = key.join(", ") || "chưa có đáp án";
    const hasKey = key.length > 0;
    const verdict = !hasKey ? "chưa có đáp án" : ok ? "đúng" : "sai";
    const tone = !hasKey ? "muted" : ok ? "ok" : "no";
    const flag = q.contested ? " · tranh chấp" : "";
    const links = traceLinks(q);
    return `
      <article class="review-item ${q.contested || !key.length ? "flagged" : ""}" data-ok="${ok}">
        <div>${q.image ? shot(q, "lazy") : ""}</div>
        <div>
          <div class="qhead" style="margin-bottom:8px">
            <span class="qnum">Câu ${q.n}${q.multi ? ` · chọn ${q.pick || "nhiều"}` : ""}</span>
            <span class="review-links">
              ${links}
              <span class="verdict ${tone}">${verdict}${flag}</span>
            </span>
          </div>
          <div class="mini-choices">
            <span class="mini you">bạn: ${esc(yours)}</span>
            <span class="mini key">đáp án: ${esc(answer)}</span>
            <span class="mini">${q.vote_count || 0} lượt bình chọn</span>
          </div>
          ${voteBars(q)}
          ${noteOf(q.n) ? `<p class="review-note">${esc(noteOf(q.n))}</p>` : ""}
        </div>
      </article>`;
  }

  /* ------------------------------------------------------------- keyboard */
  document.addEventListener("keydown", (event) => {
    if (!state.data || $("#topbar").hidden) return;
    const target = event.target;
    const tag = target && target.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    const key = event.key.toUpperCase();
    const q = question(state.queue[state.i]);
    const letters = q?.choices?.length ? q.choices : ["A", "B", "C", "D"];
    const index = "1234".indexOf(key);
    const letter = index >= 0 ? "ABCD"[index] : key;
    if (letters.includes(letter) && (index >= 0 || /^[A-D]$/.test(key))) {
      event.preventDefault();
      select(letter);
    } else if (event.key === "Enter") {
      if (tag === "BUTTON") return; // let the focused button handle Enter itself
      const n = state.queue[state.i];
      if (state.mode === "practice" && !revealed(n) && q.multi && chosen(n).size) checkAnswer();
      else if (state.i === state.queue.length - 1) finish();
      else goto(state.i + 1);
    } else if (event.key === "ArrowRight") {
      if (state.i === state.queue.length - 1) finish();
      else goto(state.i + 1);
    } else if (event.key === "ArrowLeft") {
      goto(state.i - 1);
    } else if (key === "P") {
      togglePause();
    }
  });

  boot();
})();
