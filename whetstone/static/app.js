"use strict";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const state = {
  config: null,
  tracks: [],
  trackId: null,
  challenge: null,
  hintsShown: 0,
  hintReady: true,
  notes: [],
  requests: {},
  profile: null,
  agent: { connected: false },
  noteAfter: 0,
  noteDecos: [],
  lessonLocked: false,
  activeFile: "solution.py",
  mainFile: "solution.py",  // the learner's file: solution.py, or design.md for a system design
  editor: null,
  models: {},
  useFallback: false,
  saveTimer: null,
  running: false,
  catalog: [],
  paths: [],
  pathFilter: { q: "", foryou: false, ready: false, domain: "", company: "", module: "", sort: "" },
  filters: { q: "", company: "", round: "", status: "" },
  designs: [],
  designFilter: { q: "", company: "", status: "", chosen: false },
  timer: null,
  focusOpen: false,   // Your focus: every row, or the first few
  readyOpen: false,   // Ready to start: every module, or the first few
};

/* ---------- Utilities ---------- */
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) { /* keep statusText */ }
    throw new Error(detail);
  }
  return res.json();
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

/* ---------- Marks: company logos and icons, from static/marks.js ---------- */
const SVG_NS = "http://www.w3.org/2000/svg";

function icon(name, cls = "icon") {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", cls);
  svg.setAttribute("aria-hidden", "true");
  svg.innerHTML = ICONS[name] || "";
  return svg;
}

/** "Jane Street" -> "JS", "BlackRock" -> "BR", "IBM" -> "IBM". */
function initials(name) {
  if (name.length <= 3) return name;
  const words = name.split(/\s+/);
  if (words.length > 1) return (words[0][0] + words[1][0]).toUpperCase();
  const cap = name.slice(1).match(/[A-Z]/);
  return name[0].toUpperCase() + (cap ? cap[0] : "");
}

function lightHex(hex) {
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.6;
}

/** A company's logo on its brand colour, or its initials when there is no logo. */
function companyMark(name) {
  const logo = LOGOS[name];
  if (!logo) return el("span", { class: "co co-initials", title: name }, initials(name));
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("d", logo[1]);
  svg.append(path);
  return el("span", { class: `co${lightHex(logo[0]) ? " co-light" : ""}`, title: name, style: `--co: #${logo[0]}` }, svg);
}

/** Overlapping logos: up to `max`, the last place taken by "+N" when there are more. */
function companyStack(names, max = 4) {
  if (!names.length) return null;
  const shown = names.length > max ? names.slice(0, max - 1) : names;
  const rest = names.slice(shown.length);
  return el("span", { class: "co-stack", role: "img", "aria-label": names.join(", ") }, shown.map(companyMark),
    rest.length ? el("span", { class: "co co-more", title: rest.join(", ") }, `+${rest.length}`) : null);
}

/** Each path domain's icon and colour family: money, people, search, or platforms. */
const DOMAINS = {
  "Payments & fintech": ["credit-card", "money"], "Trading & markets": ["chart-candlestick", "money"],
  "Social & media": ["users", "people"], "Messaging & collaboration": ["messages-square", "people"],
  "Marketplaces & mobility": ["car", "people"], "Search & ads": ["search", "search"],
  "AI & developer platforms": ["bot", "platform"], "Data & infrastructure": ["database", "platform"],
  "Enterprise software": ["building-2", "platform"], "Devices & industry": ["cpu", "platform"], "Foundations": ["layers", "platform"],
};

function domainTile(domain, small) {
  const [name, family] = DOMAINS[domain] || ["layers", "platform"];
  return el("span", { class: `dtile${small ? " dtile-small" : ""}`, "data-family": family, title: domain || "Other" }, icon(name));
}

function plural(n, word, many) { return `${n} ${n === 1 ? word : many || `${word}s`}`; }

/* ---------- Theme ---------- */
function initTheme() {
  let saved = null;
  try { saved = localStorage.getItem("whetstone-theme"); } catch (_) { /* storage blocked */ }
  if (saved) document.documentElement.dataset.theme = saved;
  $("#theme-toggle").addEventListener("click", () => {
    const current = document.documentElement.dataset.theme
      || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("whetstone-theme", next); } catch (_) { /* ignore */ }
    if (window.monaco) monaco.editor.setTheme(monacoTheme());
    if (state.board) renderBoard();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (window.monaco) monaco.editor.setTheme(monacoTheme());
    if (state.board) renderBoard();
  });
}

function isDark() {
  const t = document.documentElement.dataset.theme;
  return t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
}
function monacoTheme() { return isDark() ? "whetstone-dark" : "whetstone-light"; }

/* ---------- Editor ---------- */
function loadMonaco() {
  return new Promise((resolve) => {
    if (window.MONACO_FAILED || typeof require === "undefined") return resolve(false);
    const timer = setTimeout(() => resolve(false), 8000);
    window.MonacoEnvironment = {
      getWorkerUrl() {
        const src = `self.MonacoEnvironment={baseUrl:'${window.MONACO_BASE}/'};importScripts('${window.MONACO_BASE}/vs/base/worker/workerMain.js');`;
        return `data:text/javascript;charset=utf-8,${encodeURIComponent(src)}`;
      },
    };
    require.config({ paths: { vs: `${window.MONACO_BASE}/vs` } });
    require(["vs/editor/editor.main"], () => { clearTimeout(timer); resolve(true); }, () => { clearTimeout(timer); resolve(false); });
  });
}

function defineThemes() {
  // The editor follows the page: Claude Desktop's neutral grays (the app.css tokens), clay for numbers and the cursor.
  monaco.editor.defineTheme("whetstone-light", {
    base: "vs", inherit: true,
    rules: [
      { token: "comment", foreground: "646464", fontStyle: "italic" },
      { token: "keyword", foreground: "2F6497", fontStyle: "bold" },
      { token: "string", foreground: "2E7A4D" },
      { token: "number", foreground: "B8572F" },
    ],
    colors: {
      "editor.background": "#F5F5F5",
      "editor.lineHighlightBackground": "#EBEBEB",
      "editorLineNumber.foreground": "#9A9A9A",
      "editorLineNumber.activeForeground": "#363636",
      "editorCursor.foreground": "#B8572F",
      "editor.selectionBackground": "#DCE6F1",
    },
  });
  monaco.editor.defineTheme("whetstone-dark", {
    base: "vs-dark", inherit: true,
    rules: [
      { token: "comment", foreground: "8A8A8A", fontStyle: "italic" },
      { token: "keyword", foreground: "8BB4DE", fontStyle: "bold" },
      { token: "string", foreground: "6CC08B" },
      { token: "number", foreground: "E8956F" },
    ],
    colors: {
      "editor.background": "#111111",
      "editor.lineHighlightBackground": "#1F1F1F",
      "editorLineNumber.foreground": "#5A5A5A",
      "editorLineNumber.activeForeground": "#C5C5C5",
      "editorCursor.foreground": "#D97757",
      "editor.selectionBackground": "#3A4A5E",
    },
  });
}

async function initEditor() {
  const ok = await loadMonaco();
  if (!ok) {
    state.useFallback = true;
    $("#editor").hidden = true;
    const ta = $("#fallback-editor");
    ta.hidden = false;
    ta.addEventListener("input", () => { if (state.activeFile === state.mainFile) scheduleSave(); });
    ta.addEventListener("keydown", (e) => {
      if (e.key === "Tab" && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        const { selectionStart: s, selectionEnd: end, value } = ta;
        ta.value = value.slice(0, s) + "    " + value.slice(end);
        ta.selectionStart = ta.selectionEnd = s + 4;
        scheduleSave();
      }
    });
    return;
  }
  defineThemes();
  state.editor = monaco.editor.create($("#editor"), {
    language: "python",
    theme: monacoTheme(),
    automaticLayout: true,
    fontFamily: "'IBM Plex Mono', 'SF Mono', Menlo, Consolas, monospace",
    ...editorDensity(),
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    tabSize: 4,
    insertSpaces: true,
    renderWhitespace: "boundary",
    glyphMargin: true,
    padding: { top: 10 },
  });
  state.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => run("run"));
  state.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.Enter, () => run("submit"));
  // Plex Mono may arrive after Monaco measured its fallback; remeasure so the cursor lines up.
  document.fonts.ready.then(() => monaco.editor.remeasureFonts());
}

function getCode() {
  if (state.useFallback) {
    return state.fallbackShowing === state.mainFile ? $("#fallback-editor").value : state.fallbackCode;
  }
  return state.models[state.mainFile] ? state.models[state.mainFile].getValue() : "";
}

const FILE_LANG = { py: "python", md: "markdown", sh: "shell", yaml: "yaml", yml: "yaml", json: "json", ts: "typescript", js: "javascript" };
function fileLanguage(name) { return FILE_LANG[name.split(".").pop()] || "plaintext"; }

function setFiles(code, files) {
  const all = [{ name: state.mainFile, content: code, editable: true }, ...files.map((f) => ({ ...f, editable: false }))];
  if (state.useFallback) {
    state.fallbackFiles = all;
    state.fallbackCode = code;
    state.fallbackShowing = null;
  } else {
    Object.values(state.models).forEach((m) => m.dispose());
    state.models = {};
    for (const f of all) {
      const uri = monaco.Uri.parse(`file:///${state.challenge.track}/${state.challenge.id}/${f.name}`);
      const model = monaco.editor.createModel(f.content, fileLanguage(f.name), uri);
      if (f.editable) model.onDidChangeContent(() => scheduleSave());
      state.models[f.name] = model;
    }
  }
  // A design gets a rendered preview, with its Mermaid diagrams drawn.
  renderFileTabs(isBoard() ? [...all, { name: WHITEBOARD, preview: true }, { name: PREVIEW, preview: true }] : all);
  showFile(state.mainFile);
}

function renderFileTabs(files) {
  const bar = $("#file-tabs");
  bar.replaceChildren(...files.map((f) => el("button", {
    class: "file-tab", role: "tab", type: "button", "data-file": f.name,
    "aria-selected": f.name === state.activeFile ? "true" : "false",
    onclick: () => showFile(f.name),
  }, f.name, f.editable || f.preview ? null : el("span", { class: "ro", text: "read-only" }))));
}

function showFile(name) {
  const preview = name === PREVIEW;
  $(".editor-wrap").classList.toggle("previewing", preview);
  $(".editor-wrap").classList.toggle("drawing", name === WHITEBOARD);
  if (name === WHITEBOARD) {
    showWhiteboard();
  } else if (preview) {
    if (state.useFallback && state.fallbackShowing === state.mainFile) state.fallbackCode = $("#fallback-editor").value;
    renderPreview();
  } else if (state.useFallback) {
    const ta = $("#fallback-editor");
    if (state.fallbackShowing === state.mainFile) state.fallbackCode = ta.value;
    const file = state.fallbackFiles.find((f) => f.name === name);
    ta.value = name === state.mainFile ? state.fallbackCode : file.content;
    ta.readOnly = name !== state.mainFile;
    state.fallbackShowing = name;
  } else {
    state.editor.setModel(state.models[name]);
    state.editor.updateOptions({ readOnly: name !== state.mainFile, wordWrap: name.endsWith(".md") ? "on" : "off" });
  }
  state.activeFile = name;
  $$(".file-tab").forEach((t) => t.setAttribute("aria-selected", t.dataset.file === name ? "true" : "false"));
}

function scheduleSave() {
  $("#save-state").textContent = "Editing";
  clearTimeout(state.saveTimer);
  state.saveTimer = setTimeout(saveDraft, 800);
}

async function saveDraft() {
  if (!state.challenge) return;
  const { track, id } = state.challenge;
  try {
    await api(`/api/challenges/${track}/${id}/draft`, { method: "PUT", body: { code: getCode() } });
    $("#save-state").textContent = "Saved";
  } catch (err) {
    $("#save-state").textContent = `Not saved: ${err.message}`;
  }
}

/* ---------- Tracks, rail, stats ---------- */
async function loadTracks() {
  state.tracks = await api("/api/tracks");
  const select = $("#track-select");
  select.replaceChildren(...state.tracks.map((t) => el("option", { value: t.id, text: t.title })));
  select.parentElement.hidden = state.tracks.length < 2;
}

function currentTrack() { return state.tracks.find((t) => t.id === state.trackId) || state.tracks[0]; }

function renderRail() {
  const track = currentTrack();
  if (!track) return;
  $("#track-select").value = track.id;
  $("#track-desc").textContent = track.description;
  const i = state.challenge && state.challenge.track === track.id ? track.challenges.findIndex((c) => c.id === state.challenge.id) : -1;
  const step = (d) => track.challenges[i + d];
  $("#step-label").textContent = i >= 0 ? `${i + 1} / ${track.challenges.length}` : "";
  $("#prev-q").disabled = !step(-1);
  $("#next-q").disabled = !step(1);
  $("#prev-q").onclick = () => { if (step(-1)) location.hash = `#/${track.id}/${step(-1).id}`; };
  $("#next-q").onclick = () => { if (step(1)) location.hash = `#/${track.id}/${step(1).id}`; };
  const list = $("#rail-list");
  list.replaceChildren(...track.challenges.map((c) => {
    const statusText = STATUS_TEXT[c.status];
    const isCurrent = state.challenge && state.challenge.track === track.id && state.challenge.id === c.id;
    return el("li", { class: "rail-item", "data-status": c.status, "aria-current": isCurrent ? "true" : "false" },
      el("a", { href: `#/${track.id}/${c.id}`, "aria-label": `${c.number}. ${c.title}, ${c.difficulty}, ${statusText}` },
        el("span", { class: "notch", "aria-hidden": "true" }, ["solved", "assisted", "mastered"].includes(c.status) ? "✓" : String(c.number)),
        el("span", {},
          el("span", { class: "rail-title", text: c.title }),
          el("span", { class: "rail-sub", text: `${capital(c.difficulty)}, ${c.minutes} min${c.requires.length ? `, needs ${c.requires.join(", ")}` : ""}` }))));
  }));
}

function capital(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

/** The rail's "Last 4 weeks" calendar. */
function isoDay(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function shortDate(iso) {
  return new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/* ---------- Challenge ---------- */
async function openChallenge(trackId, cid) {
  if (state.challenge && !state.running) await saveDraft();
  unmountBoard();
  const c = await api(`/api/challenges/${trackId}/${cid}`);
  state.challenge = c;
  state.trackId = trackId;
  state.hintsShown = c.hints.length;
  state.guessing = null;
  state.hintReady = c.hint_ready;
  // Problem first: some lessons open only after the first test run (docs/PEDAGOGY.md, rule 1).
  state.lessonLocked = c.lesson_mode === "after-run" && c.runs === 0 && !c.solved;
  state.mainFile = c.file;
  state.activeFile = c.file;
  document.title = `${c.title} · Whetstone`;

  $("#challenge-title").textContent = c.title;
  const meta = [el("span", { class: "diff", "data-d": c.difficulty, text: capital(c.difficulty) }), el("span", { text: `About ${c.minutes} min` })];
  if (TYPE_LABEL[c.type]) meta.unshift(el("span", { class: "qtype" }, icon(TYPE_ICON[c.type]), TYPE_LABEL[c.type]));
  if (c.requires.includes("redis")) {
    const ok = state.config && state.config.redis_ok;
    meta.push(el("span", { class: `needs${ok ? " ok" : ""}`, text: ok ? "Redis connected" : "Needs Redis: not reachable" }));
  }
  meta.push(...c.tags.map((t) => el("span", { class: "tag", text: t })));
  $("#challenge-meta").replaceChildren(...meta);

  renderLesson();
  $("#panel-problem").innerHTML = c.problem_html;
  colorize($("#panel-problem"));
  buildPeek();
  $("#hint-list").replaceChildren(...c.hints.map((html) => { const li = el("li"); li.innerHTML = html; return li; }));
  colorize($("#hint-list"));
  setupBoard(c);
  updateHintButton();
  updateSolutionGate();
  $("#solution-code").hidden = true;
  $("#solution-doc").hidden = true;
  selectTab(c.runs > 0 || state.lessonLocked ? "problem" : "lesson");

  setFiles(c.code, c.files);
  $("#save-state").textContent = c.code !== c.starter ? "Draft restored" : "";
  clearResults();
  $("#results").replaceChildren(el("p", { class: "results-empty", text: isBoard()
    ? "Check your sections to see what is still empty. When the design is done, ask your agent for a review: it grades the design against a rubric, point by point."
    : c.solved
      ? "You solved this one. Run it again any time, or try a cleaner solution."
      : "Run the tests to see results here. Visible tests check the basics. Submit also runs hidden tests for edge cases." }));
  if (c.review) renderReview(c.review);
  renderRail();
  $(".reader-body").scrollTop = 0;
  state.notes = [];
  state.noteAfter = 0;
  renderNotes();
  pollNotes();
}

/* ---------- Agent inbox ---------- */
// Build buttons queue a request; the learner's own agent, watching with `whetstone watch`,
// claims it and reports back. Whetstone never starts an agent itself.
const REQUEST_LABEL = {
  build: "Prepare", variant: "Prepare review variant", "fill-path": "Prepare all missing modules", review: "Ask for a review",
  profile: "Set up my profile", design: "Prepare", grade: "Ask for review",
};
const REVIEWING = new Set(["review", "grade"]);
const RECENT_MS = 10 * 60 * 1000;

function requestButton(kind, target, label) {
  const wrap = el("span", { class: "req", "data-req": `${kind}:${target}`, "data-label": label || REQUEST_LABEL[kind] });
  renderRequest(wrap);
  return wrap;
}

function renderRequest(wrap) {
  const key = wrap.dataset.req;
  const [kind, ...rest] = key.split(":");
  const target = rest.join(":");
  const r = state.requests[key] || (kind === "build" && olderFill(target));
  const button = (text, cls, onclick) => el("button", { type: "button", class: `btn ${cls}`, onclick }, text);
  let nodes;
  if (kind === "fill-path") {
    // One build request per module, so each module shows its own state and opens as soon as it is ready.
    const p = state.paths.find((x) => x.id === target);
    const missing = p ? p.modules.filter((m) => !m.built) : [];
    const left = missing.filter((m) => !state.requests[`build:${m.module}`] && !olderFill(m.module)).length;
    nodes = left ? [button(left < missing.length ? `Prepare the other ${plural(left, "module")}` : wrap.dataset.label, "btn-secondary", () => prepareAll(target))]
      : [el("span", { class: "req-state working", text: "Your agent prepares them in order. Each one shows Start as soon as it is ready." })];
  } else if (!r) {
    nodes = [button(wrap.dataset.label, kind === "grade" ? "btn-primary" : "btn-secondary", () => sendRequest(kind, target))];
  } else if (r.status === "queued") {
    nodes = [el("span", { class: "req-state", text: state.agent.connected ? "Queued for your agent" : "Waiting for your agent" }),
      button("Cancel", "btn-text", () => cancelRequest(r.id))];
  } else if (r.status === "claimed") {
    nodes = [el("span", { class: "req-state working", text: REVIEWING.has(kind) ? "Your agent is reviewing…" : "Your agent is preparing it…" })];
  } else if (r.status === "done" && REVIEWING.has(kind)) {
    nodes = [el("span", { class: "req-state done", text: "Reviewed" }), button("Ask again", "btn-text", () => sendRequest(kind, target))];
  } else if (r.status === "done") {
    nodes = r.result && r.result.includes("/") ? [el("a", { class: "btn btn-primary", href: `#/${r.result}` }, "Start")] : [el("span", { class: "req-state done", text: "Done" })];
  } else {
    nodes = [el("span", { class: "req-state failed", text: `${REVIEWING.has(kind) ? "Not reviewed" : "Not prepared"}: ${r.result || "your agent could not do it."}` }),
      button("Try again", "btn-text", () => sendRequest(kind, target))];
  }
  wrap.replaceChildren(...nodes);
}

async function sendRequest(kind, target) {
  try {
    if (kind === "grade") await Promise.all([saveDraft(), state.board && saveBoard()]);  // the agent grades what is saved
    const r = await api("/api/requests", { method: "POST", body: { kind, target } });
    state.requests[`${kind}:${r.target}`] = r;
    $$(".req").forEach(renderRequest);
    if (!state.agent.connected) showAgentHint();
  } catch (err) {
    showAppError(err);
  }
}

/** An open whole-path request, queued before Prepare all became one build per module, covers each module in its path. */
function olderFill(module) {
  return Object.values(state.requests).find((r) => r.kind === "fill-path" && (r.status === "queued" || r.status === "claimed")
    && ((state.paths || []).find((p) => p.id === r.target) || { modules: [] }).modules.some((m) => m.module === module));
}

/** Queue a build for each module that is not ready, in path order: the agent takes the oldest first. */
async function prepareAll(pathId) {
  const p = state.paths.find((x) => x.id === pathId);
  for (const m of p ? p.modules : []) if (!m.built && !state.requests[`build:${m.module}`]) await sendRequest("build", m.module);
}

async function cancelRequest(id) {
  await api(`/api/requests/${id}/cancel`, { method: "POST", body: {} });
  await pollRequests();
}

/** The latest request per kind and target. Finished ones count only while they are fresh. */
async function pollRequests() {
  let data;
  try { data = await api("/api/requests"); } catch (_) { return; }
  const before = state.requests;
  const now = Date.now();
  const next = {};
  for (const r of data.requests) {
    const key = `${r.kind}:${r.target}`;
    if (key in next) continue;
    const open = r.status === "queued" || r.status === "claimed";
    next[key] = r.status !== "cancelled" && (open || now - new Date(r.updated_at).getTime() < RECENT_MS) ? r : null;
  }
  for (const key of Object.keys(next)) if (!next[key]) delete next[key];
  state.requests = next;
  state.agent = data.agent;
  renderAgentStatus();
  $$(".req").forEach(renderRequest);
  // A request that just finished built something: refresh what the page shows.
  const finished = Object.values(next).some((r) => r.status === "done" && (before[`${r.kind}:${r.target}`] || {}).status !== "done");
  if (finished && Object.keys(before).length) {
    await loadTracks();
    if (!$("#home").hidden) await loadHome();
    else if (!$("#paths").hidden) await loadPaths();
    else if (!$("#design").hidden) await loadDesign();
    const drawer = $("#path-dialog");
    const shown = drawer.open && state.paths.find((x) => x.id === drawer.dataset.path);
    if (shown) $("#path-detail").replaceChildren(pathCard(shown));  // a module it lists may be ready now
    const c = state.challenge;
    const graded = c && next[`grade:${c.track}/${c.id}`];
    if (graded && graded.status === "done" && (before[`grade:${c.track}/${c.id}`] || {}).status !== "done" && !$("#workspace").hidden) await refreshReview();
  }
}

function renderAgentStatus() {
  const box = $("#agent-status");
  box.dataset.connected = String(Boolean(state.agent.connected));
  box.title = state.agent.connected
    ? "Your agent is watching Whetstone. Prepare buttons go straight to it."
    : "No agent is watching. Start your agent in this folder and say: watch Whetstone";
  box.replaceChildren(el("span", { class: "agent-dot", "aria-hidden": "true" }), el("span", { class: "agent-label", text: state.agent.connected ? "Agent connected" : "No agent" }));
}

function showAgentHint() {
  const box = $("#app-error");
  box.classList.add("info");
  box.replaceChildren(
    el("strong", { text: "Queued. " }),
    "Your agent picks this up while it watches Whetstone. In your agent, in this folder, say: ",
    el("code", { text: "watch Whetstone" }),
    el("button", { type: "button", class: "btn btn-text btn-small", onclick: () => { box.hidden = true; box.classList.remove("info"); } }, "Dismiss"));
  box.hidden = false;
}

/* ---------- Live pair: notes from the learner's agent ---------- */
// The agent watches with `bin/whetstone watch` and replies with `bin/whetstone note`.
async function pollNotes() {
  const c = state.challenge;
  if (!c || document.hidden || $("#workspace").hidden) return;
  try {
    const fresh = await api(`/api/challenges/${c.track}/${c.id}/notes?after=${state.noteAfter}`);
    if (state.challenge !== c || !fresh.length) return;
    state.notes.push(...fresh);
    state.noteAfter = fresh[fresh.length - 1].id;
    renderNotes();
  } catch (_) { /* the next poll retries */ }
}

function renderNotes() {
  const shown = state.notes.slice(-3);
  $("#pair-notes").replaceChildren(...shown.map((n) => el("li", { class: "pair-note" },
    el("span", { class: "pair-who", text: "Your agent" }),
    el("button", { type: "button", class: "btn btn-icon pair-dismiss", "aria-label": "Dismiss note", onclick: () => dismissNote(n.id) }, "×"),
    el("p", { text: n.text }),
    n.line ? el("button", { type: "button", class: "btn btn-text pair-line-link", onclick: () => goToLine(n.line) }, `Line ${n.line}`) : null)));
  $(".tab-code").toggleAttribute("data-notes", state.notes.length > 0);
  if (state.editor && window.monaco) {
    state.noteDecos = state.editor.deltaDecorations(state.noteDecos, state.notes.filter((n) => n.line).map((n) => ({
      range: new monaco.Range(n.line, 1, n.line, 1),
      options: { isWholeLine: true, className: "pair-line", glyphMarginClassName: "pair-glyph", glyphMarginHoverMessage: { value: n.text }, hoverMessage: { value: n.text } },
    })));
  }
}

async function dismissNote(id) {
  state.notes = state.notes.filter((n) => n.id !== id);
  renderNotes();
  try { await api(`/api/notes/${id}`, { method: "POST", body: { dismissed: true } }); } catch (_) { /* already hidden here */ }
}

function goToLine(line) {
  selectTab("code");
  showFile(state.mainFile);
  if (state.editor) { state.editor.revealLineInCenter(line); state.editor.setPosition({ lineNumber: line, column: 1 }); state.editor.focus(); }
}

async function initPair() {
  const select = $("#pair-mode");
  try { select.value = (await api("/api/pair")).mode; } catch (_) { /* keep the default */ }
  select.addEventListener("change", () => api("/api/pair", { method: "PUT", body: { mode: select.value } }));
  setInterval(pollNotes, 3000);
  renderAgentStatus();
  pollRequests();
  setInterval(() => { if (!document.hidden) pollRequests(); }, 4000);
}

function selectTab(name) {
  $$(".tab").forEach((t) => t.setAttribute("aria-selected", t.dataset.tab === name ? "true" : "false"));
  $$("[data-panel]").forEach((p) => { p.hidden = p.dataset.panel !== name; });
  // Narrow layouts (a side pane, a phone) show one column: the Code tab swaps the reading
  // panel for the editor and test results.
  $("#workspace").classList.toggle("code-view", name === "code");
  if (name === "code" && state.editor) requestAnimationFrame(() => state.editor.focus());
}

/* ---------- Narrow layouts ---------- */
const PANE = matchMedia("(max-width: 1099px)");
const PHONE = matchMedia("(max-width: 640px)");

function editorDensity() {
  return PANE.matches
    ? { fontSize: 12.5, lineHeight: 19, lineNumbersMinChars: 3, folding: false, wordWrap: PHONE.matches ? "on" : "off" }
    : { fontSize: 13.5, lineHeight: 21, lineNumbersMinChars: 5, folding: true, wordWrap: "off" };
}

function onLayoutChange() {
  if (state.editor) state.editor.updateOptions(editorDensity());
  // The Code tab only exists in narrow layouts; widening the window shows both columns again.
  const current = $(".tab[aria-selected='true']");
  if (!PANE.matches && current && current.dataset.tab === "code") selectTab("problem");
}

/* ---------- Problem sections over the editor (narrow layouts) ---------- */
// In a side pane the Code view lists the problem's sections. Hover one to read it over the
// editor while you keep typing; click to keep it open until you click elsewhere or press Escape.
const peek = { pinned: false, timer: 0 };

/** One chip per "## Section" of the problem; text before the first heading is "Problem". */
function buildPeek() {
  const sections = [];
  for (const node of $("#panel-problem").children) {
    const heading = node.tagName === "H2";
    if (heading || !sections.length) sections.push({ title: heading ? node.textContent : "Problem", nodes: [] });
    if (!heading) sections.at(-1).nodes.push(node);
  }
  hidePeek();
  $("#peek-row").replaceChildren(...sections.filter((x) => x.nodes.length).map((x) => {
    const chip = el("button", { type: "button", class: "chip", "aria-expanded": "false", "aria-controls": "peek-pop" }, x.title);
    chip.section = x;
    return chip;
  }));
}

function showPeek(chip, pinned) {
  const pop = $("#peek-pop");
  pop.replaceChildren(...chip.section.nodes.map((n) => n.cloneNode(true)));  // clone late: code is coloured by now
  pop.setAttribute("aria-label", chip.section.title);
  $$("#peek-row .chip").forEach((c) => c.setAttribute("aria-expanded", String(c === chip)));
  pop.style.top = `${$("#peek-row").getBoundingClientRect().bottom + 6}px`;
  peek.pinned = pinned;
  if (!pop.matches(":popover-open")) pop.showPopover();
  pop.scrollTop = 0;
}

function hidePeek() {
  clearTimeout(peek.timer);
  peek.pinned = false;
  const pop = $("#peek-pop");
  if (pop.matches(":popover-open")) pop.hidePopover();
  $$("#peek-row .chip").forEach((c) => c.setAttribute("aria-expanded", "false"));
}

function initPeek() {
  const row = $("#peek-row"), pop = $("#peek-pop");
  row.addEventListener("pointerover", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip || e.pointerType !== "mouse" || peek.pinned) return;
    clearTimeout(peek.timer);
    peek.timer = setTimeout(() => showPeek(chip, false), 150);
  });
  const leave = () => {
    clearTimeout(peek.timer);
    peek.timer = setTimeout(() => { if (!peek.pinned && !row.matches(":hover") && !pop.matches(":hover")) hidePeek(); }, 250);
  };
  row.addEventListener("pointerleave", leave);
  pop.addEventListener("pointerleave", leave);
  row.addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    clearTimeout(peek.timer);
    if (peek.pinned && chip.getAttribute("aria-expanded") === "true") hidePeek();
    else showPeek(chip, true);
  });
  document.addEventListener("pointerdown", (e) => { if (!row.contains(e.target) && !pop.contains(e.target)) hidePeek(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") hidePeek(); }, true);
}

/** Colour the code blocks in lessons, problems, hints and the solution with the editor's own
    tokenizer, so they match the editor theme and need no extra library. */
const LANG = { py: "python", sh: "shell", bash: "shell", console: "shell", js: "javascript", ts: "typescript", yml: "yaml" };
async function colorize(root, fallback) {
  if (!window.monaco || state.useFallback) return;
  for (const code of root.querySelectorAll("pre code:not([data-colored])")) {
    const lang = (code.className.match(/language-([\w+-]+)/) || [])[1] || fallback;
    if (!lang) continue;
    code.dataset.colored = "1";
    try {
      code.innerHTML = await monaco.editor.colorize(code.textContent.replace(/\n$/, ""), LANG[lang] || lang, { tabSize: 4 });
    } catch (_) { /* an unknown language stays plain */ }
  }
}

function renderLesson() {
  const panel = $("#panel-lesson");
  if (state.lessonLocked) {
    panel.replaceChildren(el("p", { class: "panel-intro", text: `Try the problem first. The lesson opens after your first ${isBoard() ? "section check" : "test run"}: attempting it before reading makes the idea stick.` }));
  } else {
    panel.innerHTML = state.challenge.lesson_html;
    colorize(panel);
  }
}

// Hints are a ladder: each rung unlocks after a test run since the last one (docs/PEDAGOGY.md, rule 5).
function updateHintButton() {
  const btn = $("#next-hint");
  const total = state.challenge ? state.challenge.hint_count : 0;
  btn.hidden = state.hintsShown >= total;
  btn.disabled = !state.hintReady;
  btn.textContent = state.hintReady
    ? `Show hint ${state.hintsShown + 1} of ${total}`
    : `Hint ${state.hintsShown + 1} unlocks after your next ${isBoard() ? "section check" : "test run"}`;
}

async function showNextHint() {
  const { track, id } = state.challenge;
  try {
    const h = await api(`/api/challenges/${track}/${id}/hints/${state.hintsShown}`);
    const li = el("li");
    li.innerHTML = h.html;
    colorize(li);
    $("#hint-list").append(li);
    state.hintsShown += 1;
    state.hintReady = false;
  } catch (_) {
    state.hintReady = false;
  }
  updateHintButton();
}

function updateSolutionGate() {
  const open = state.challenge.solution_open;
  $("#solution-gate").hidden = false;
  const board = isBoard();
  $("#solution-intro").textContent = open
    ? board ? "Compare the reference design with yours. Name one decision it makes differently, and why." : "Compare the reference with your code. Name one difference, and why it matters."
    : board
      ? "The reference design opens after your agent's review passes. If you are truly stuck, you can give up and open it now. Passing the review after that counts as solved with help, and a variant comes back 2 days later."
      : "The reference opens after you solve it. If you are truly stuck, you can give up and open it now. Passing the tests after that counts as solved with help, and a variant comes back 2 days later.";
  $("#reveal-solution").textContent = open ? `Show the reference ${board ? "design" : "solution"}` : `I give up: show the ${board ? "design" : "solution"}`;
}

async function revealSolution() {
  const { track, id, solution_open: open } = state.challenge;
  if (!open && !confirm(`Give up and see the reference ${isBoard() ? "design" : "solution"}? Solving it afterwards counts as solved with help.`)) return;
  const s = await api(`/api/challenges/${track}/${id}/solution`, { method: "POST", body: { give_up: !open } });
  state.challenge.solution_open = true;
  $("#solution-gate").hidden = true;
  if (s.lesson_html) { state.challenge.lesson_html = s.lesson_html; renderLesson(); }  // predict: the misconceptions open
  if (s.html) {
    const doc = $("#solution-doc");
    doc.innerHTML = s.html;
    doc.hidden = false;
    await renderMermaid(doc);
    colorize(doc);
    if (isBoard() && state.challenge.review) refreshReview();  // the rubric's hidden points open too
    return;
  }
  const pre = $("#solution-code");
  const code = pre.querySelector("code");
  code.textContent = s.code;
  delete code.dataset.colored;
  colorize(pre, "python");
  pre.hidden = false;
}

async function resetCode() {
  if (!confirm("Replace your code with the starter code? Your current draft will be lost.")) return;
  const { track, id } = state.challenge;
  const r = await api(`/api/challenges/${track}/${id}/reset`, { method: "POST" });
  if (state.useFallback) {
    state.fallbackCode = r.code;
    if (state.activeFile === state.mainFile) $("#fallback-editor").value = r.code;
  } else {
    state.models[state.mainFile].setValue(r.code);
  }
  showFile(state.mainFile);
  $("#save-state").textContent = "Reset to starter";
}

/* ---------- Running tests ---------- */
const STATUS_TEXT = { new: "not started", attempted: "in progress", assisted: "solved with help", solved: "solved", mastered: "mastered" };
const TYPE_LABEL = { predict: "Predict", fix: "Fix the bug", review: "Review", tests: "Write the tests", design: "Design", whiteboard: "System design" };
const TYPE_ICON = { predict: "eye", fix: "wrench", review: "scan-search", tests: "flask-conical", design: "pen-tool", whiteboard: "presentation" };
const VERDICT = { passed: "Passed", failed: "Not yet", error: "Could not run", timeout: "Timed out", blocked: "Blocked" };

/* ---------- Predict then explain (docs/PEDAGOGY.md, rule 8) ---------- */
const PREDICT_KEY = "whetstone.predict";
function predictOn() { try { return localStorage.getItem(PREDICT_KEY) !== "off"; } catch (_) { return true; } }
function setPredict(on) { try { localStorage.setItem(PREDICT_KEY, on ? "on" : "off"); } catch (_) { /* per-viewer only */ } }

// Ask on the first run of a question, and before each Submit until it is solved.
function wantsGuess(mode) {
  const c = state.challenge;
  if (!predictOn() || isBoard()) return false;
  return mode === "run" ? c.runs === 0 && c.visible_tests.length > 0 : !c.solved;
}

function showGuess(mode) {
  const c = state.challenge;
  const go = (guess) => { state.guessing = null; run(mode, guess); };
  showResults("predict", "Your guess");
  let body, send;
  if (mode === "run") {
    const guess = {};
    body = el("ul", { class: "guess-list" }, c.visible_tests.map((t) => {
      const pick = (v, label) => el("button", { type: "button", class: "chip", "aria-pressed": "false", onclick: (e) => {
        guess[t.name] = v;
        e.target.parentElement.querySelectorAll(".chip").forEach((b) => b.setAttribute("aria-pressed", String(b === e.target)));
      } }, label);
      return el("li", { class: "guess-row" }, el("span", { text: t.label }), el("span", { class: "guess-pick" }, pick(true, "Pass"), pick(false, "Fail")));
    }));
    send = () => go(Object.keys(guess).length ? { tests: guess } : null);
  } else {
    let allPass = null, sure = 3;
    const chips = (items, onPick, current) => el("span", { class: "guess-pick" }, items.map(([v, label]) => el("button", {
      type: "button", class: "chip", "aria-pressed": String(v === current), onclick: (e) => {
        onPick(v);
        e.target.parentElement.querySelectorAll(".chip").forEach((b) => b.setAttribute("aria-pressed", String(b === e.target)));
      } }, label)));
    body = el("ul", { class: "guess-list" },
      el("li", { class: "guess-row" }, el("span", { text: c.type === "tests" ? "Your tests will catch every hidden bug" : "Every hidden test will pass" }), chips([[true, "Yes"], [false, "No"]], (v) => { allPass = v; }, null)),
      el("li", { class: "guess-row" }, el("span", { text: "How sure are you?" }), chips([1, 2, 3, 4, 5].map((n) => [n, String(n)]), (v) => { sure = v; }, 3)));
    send = () => go(allPass === null ? null : { all_pass: allPass, confidence: sure });
  }
  state.guessing = { mode, send };
  $("#results").replaceChildren(el("div", { class: "predict" },
    el("p", { class: "predict-q", text: mode === "run" ? "Before you run: which tests will pass?" : c.type === "tests" ? "Before you submit: will your tests catch the hidden bugs?" : "Before you submit: what will the hidden tests say?" }),
    el("p", { class: "home-sub", text: "Guessing first trains you to read code before you run it. Mark only what you are sure about." }),
    body,
    el("div", { class: "predict-actions" },
      el("button", { type: "button", class: "btn btn-primary", onclick: send }, mode === "run" ? "Run with my guess" : "Submit with my guess"),
      el("button", { type: "button", class: "btn btn-text", onclick: () => go(null) }, "Skip"),
      el("button", { type: "button", class: "btn btn-text", onclick: () => { setPredict(false); go(null); } }, "Stop asking"))));
}

function guessLine(p) {
  if (!p || !p.total) return null;
  if (p.details.length === 0) {
    const tests = state.challenge.type === "tests";
    const said = p.all_pass ? (tests ? "your tests would catch every hidden bug" : "every hidden test would pass") : (tests ? "some hidden bug would slip past your tests" : "some hidden test would fail");
    return el("p", { class: "prediction-note", "data-right": String(Boolean(p.correct)) },
      `You said ${said}${p.confidence ? `, ${p.confidence} of 5 sure` : ""}. ${p.correct ? "Right." : "Not this time."}`);
  }
  const misses = p.details.filter((d) => d.predicted !== d.actual).slice(0, 3)
    .map((d) => `you expected “${d.label}” to ${d.predicted ? "pass" : "fail"}, and it ${d.actual ? "passed" : "failed"}`);
  return el("p", { class: "prediction-note", "data-right": String(p.correct === p.total) },
    `Your guess: ${p.correct} of ${p.total} right.${misses.length ? ` ${capital(misses.join("; "))}.` : ""}`);
}

/** After a solve: one question about a hidden case, answered in your own words. */
function explainBox(r) {
  const passed = r.tests.filter((t) => t.outcome === "passed");
  const pool = passed.filter((t) => t.hidden).length ? passed.filter((t) => t.hidden) : passed;
  if (!pool.length || !predictOn()) return null;
  const t = pool[Math.floor(Math.random() * pool.length)];
  const text = el("textarea", { rows: "2", placeholder: "One or two sentences, in your own words.", "aria-label": "Your explanation" });
  const box = el("div", { class: "explain" },
    el("label", { class: "predict-q", text: `One question: why does your code handle “${t.label}”?` }),
    text,
    el("div", { class: "predict-actions" },
      el("button", { type: "button", class: "btn btn-secondary", onclick: async () => {
        if (!text.value.trim()) { text.focus(); return; }
        const { track, id } = state.challenge;
        await api(`/api/challenges/${track}/${id}/explanation`, { method: "POST", body: { test: t.name, text: text.value } });
        box.replaceChildren(el("p", { class: "home-sub", text: "Saved. Your agent reads it when it reviews your work or tutors you." }));
      } }, "Save"),
      el("button", { type: "button", class: "btn btn-text", onclick: () => box.remove() }, "Skip")));
  return box;
}

async function run(mode, guess) {
  if (!state.challenge || state.running) return;
  if (state.board && state.board.timer) await saveBoard();
  if (isBoard() && mode === "submit") {  // a design is graded by the agent, not by tests
    const ask = $("#review-req button");
    if (ask) ask.click();
    return;
  }
  if (guess === undefined && state.guessing && state.guessing.mode === mode) { state.guessing.send(); return; }
  if (guess === undefined && wantsGuess(mode)) { showGuess(mode); return; }
  state.guessing = null;
  state.running = true;
  clearTimeout(state.saveTimer);
  const runBtn = $("#run-btn"), subBtn = $("#submit-btn");
  runBtn.disabled = subBtn.disabled = true;
  // Set only the leading text node, so the shortcut hint inside the button survives.
  (mode === "run" ? runBtn : subBtn).firstChild.nodeValue = isBoard() ? "Checking… " : mode === "run" ? "Running… " : "Submitting… ";
  showResults("running", isBoard() ? "Checking…" : "Running…");
  $("#results").replaceChildren(el("p", { class: "results-empty", text: isBoard() ? "Checking your sections…" : mode === "run" ? "Running the visible tests…" : "Running all tests, including hidden ones…" }));
  try {
    const { track, id } = state.challenge;
    const report = await api(`/api/challenges/${track}/${id}/run`, { method: "POST", body: { code: getCode(), mode, prediction: guess || null } });
    state.challenge.runs += 1;
    if (report.first_solve) state.challenge.solved = true;
    renderReport(report, mode);
    $("#save-state").textContent = "Saved";
    state.hintReady = true;
    updateHintButton();
    if (state.lessonLocked) { state.lessonLocked = false; renderLesson(); }
    if (report.lesson_html) { state.challenge.lesson_html = report.lesson_html; renderLesson(); }  // predict: the misconceptions open
    if (report.first_solve) { state.challenge.solution_open = true; updateSolutionGate(); }
    await loadTracks().then(renderRail);
  } catch (err) {
    $("#results").replaceChildren(el("p", { class: "results-empty", text: `The run failed: ${err.message}` }));
    showResults("error", "Could not run");
  } finally {
    state.running = false;
    runBtn.disabled = subBtn.disabled = false;
    runBtn.firstChild.nodeValue = isBoard() ? "Check sections " : "Run tests ";
    subBtn.firstChild.nodeValue = "Submit ";
  }
}

/** In narrow layouts the results panel only exists after a run; the chip in the action bar
    shows the verdict and hides or shows the panel so the editor can have the full height. */
function showResults(status, word, count) {
  const bench = $(".bench"), chip = $("#results-toggle");
  bench.classList.add("has-results");
  bench.classList.remove("results-hidden");
  chip.dataset.status = status;
  // On phones only the count shows; the color still carries the verdict.
  chip.replaceChildren(el("span", { class: "chip-word", text: count ? `${word} ` : word }), ...(count ? [el("span", { text: count })] : []));
  chip.setAttribute("aria-expanded", "true");
}

function clearResults() {
  $(".bench").classList.remove("has-results", "results-hidden");
}

function toggleResults() {
  const hidden = $(".bench").classList.toggle("results-hidden");
  $("#results-toggle").setAttribute("aria-expanded", hidden ? "false" : "true");
}

function renderReport(r, mode) {
  showResults(r.status, VERDICT[r.status] || r.status, `${r.passed}/${r.total}`);
  const box = $("#results");
  const nodes = [guessLine(r.prediction)].filter(Boolean);
  if (r.first_solve) nodes.push(el("p", { class: "solved-note", text: r.solve === "assisted"
    ? "Solved with help. A variant of this question comes back for review in 2 days."
    : "Solved on your own. A variant comes back for review in 3 days, to make it stick." }));
  if (r.first_solve) nodes.push(explainBox(r) || "");
  nodes.push(el("div", { class: "verdict", "data-status": r.status },
    el("span", { class: "verdict-word", text: VERDICT[r.status] || r.status }),
    el("span", { class: "verdict-sum", text: isBoard() ? r.summary : `${r.summary} (${r.duration.toFixed(1)} s)` })));

  if (r.tests.length) {
    nodes.push(el("div", { class: "strip", "aria-hidden": "true" },
      r.tests.map((t, i) => el("span", { class: `mark ${t.outcome}${t.hidden ? " hidden" : ""}`, style: `--i:${i}`, title: t.label }))));
    const sorted = [...r.tests].sort((a, b) => rank(a) - rank(b) || Number(a.hidden) - Number(b.hidden));
    nodes.push(el("ul", { class: "test-list" }, sorted.map(testRow)));
  }
  if (r.output && (r.status === "error" || r.status === "timeout" || !r.tests.length)) {
    nodes.push(el("pre", { class: "trace", text: r.output }));
  } else if (r.output) {
    nodes.push(el("details", { class: "raw-toggle" }, el("summary", { text: "Show raw pytest output" }), el("pre", { class: "trace", text: r.output })));
  }
  box.replaceChildren(...nodes);
  box.scrollTop = 0;
}

function rank(t) { return { failed: 0, error: 0, skipped: 1, passed: 2 }[t.outcome] ?? 3; }

function testRow(t) {
  const name = el("span", { class: "test-name" }, t.label, t.hidden ? el("span", { class: "vis", text: "hidden" }) : null);
  const time = isBoard() ? null : el("span", { class: "test-time", text: `${(t.duration * 1000).toFixed(0)} ms` });
  const dot = el("span", { class: `dot ${t.outcome}`, "aria-label": t.outcome });
  if (t.outcome === "passed") {
    return el("li", { class: "test-row" }, el("div", { class: "test-line" }, dot, name, time));
  }
  return el("li", { class: "test-row" },
    el("details", { open: t.outcome !== "skipped" },
      el("summary", {}, dot, name, time),
      t.message ? el("p", { class: "test-msg", text: t.message }) : null,
      t.details ? el("pre", { class: "trace", text: t.details }) : null));
}

/* ---------- System design: the scratchpad ---------- */
// A "whiteboard" question is a design interview. The learner writes Markdown with Mermaid
// diagrams; Check counts what is still empty, and their own agent grades the design against a
// rubric (`whetstone grade`), which the app shows like test results.
const PREVIEW = "Preview";
const WHITEBOARD = "Whiteboard";
const EXCALIDRAW = "https://esm.sh/@excalidraw/excalidraw@0.18.1";
let excalidrawLoad = null;

/** Excalidraw and React, as ES modules from esm.sh (React comes through the import map in
    index.html). Loaded the first time a whiteboard opens. */
function loadExcalidraw() {
  excalidrawLoad ??= (async () => {
    document.head.append(el("link", { rel: "stylesheet", href: `${EXCALIDRAW}/dist/prod/index.css` }));
    // Monaco's AMD loader sets define.amd, and a library inside Excalidraw then registers itself
    // with it instead of loading (its fonts break). Hide the flag while the modules evaluate.
    const amd = window.define && window.define.amd;
    if (amd) window.define.amd = undefined;
    try {
      const [react, client, X] = await Promise.all([import("react"), import("react-dom/client"), import(`${EXCALIDRAW}?external=react,react-dom`)]);
      return { React: react.default || react, createRoot: client.createRoot, X };
    } finally {
      if (amd) window.define.amd = amd;
    }
  })().catch(() => { excalidrawLoad = null; return null; });
  return excalidrawLoad;
}

async function showWhiteboard() {
  const c = state.challenge;
  const key = `${c.track}/${c.id}`;
  if (state.board && state.board.key === key) return;
  const box = $("#whiteboard");
  box.replaceChildren(el("p", { class: "results-empty board-note", text: "Opening the whiteboard…" }));
  const [lib, drawing] = await Promise.all([loadExcalidraw(), api(`/api/challenges/${c.track}/${c.id}/drawing`)]);
  if (state.challenge !== c || state.board) return;
  if (!lib) {
    box.replaceChildren(el("p", { class: "results-empty board-note", text: "The whiteboard needs Excalidraw from esm.sh, which did not load. Check the connection and open this tab again, or draw in a ```mermaid block in design.md." }));
    return;
  }
  const mount = el("div", { class: "board-mount" });
  box.replaceChildren(mount);
  state.board = { key, lib, root: lib.createRoot(mount), elements: drawing.elements, sig: boardSignature(drawing.elements), timer: null };
  renderBoard();
}

function renderBoard() {
  const b = state.board;
  const { React, X } = b.lib;
  b.root.render(React.createElement(X.Excalidraw, {
    theme: isDark() ? "dark" : "light",
    // A transparent canvas shows the board's own background, so it matches the app in either theme.
    initialData: { elements: b.elements, appState: { viewBackgroundColor: "transparent" }, scrollToContent: true },
    onChange: boardChanged,
    excalidrawAPI: (api) => { b.api = api; },  // for scripts, such as the README screenshots
    // No images: they bloat the drawing and the agent cannot read them.
    UIOptions: { canvasActions: { loadScene: false, saveToActiveFile: false, export: false, toggleTheme: false, changeViewBackgroundColor: false }, tools: { image: false } },
  }));
}

function boardSignature(elements) { return `${elements.length}:${elements.reduce((n, e) => n + (e.version || 0), 0)}`; }

/** Excalidraw calls this on every pointer move; save only when an element changed. */
function boardChanged(elements) {
  const b = state.board;
  const sig = boardSignature(elements);
  if (!b || sig === b.sig) return;
  b.sig = sig;
  b.elements = elements;
  $("#save-state").textContent = "Editing";
  clearTimeout(b.timer);
  b.timer = setTimeout(saveBoard, 1000);
}

async function saveBoard() {
  const b = state.board;
  if (!b) return;
  clearTimeout(b.timer);
  b.timer = null;
  try {
    await api(`/api/challenges/${b.key}/drawing`, { method: "PUT", body: { elements: b.elements } });
    $("#save-state").textContent = "Saved";
  } catch (err) {
    $("#save-state").textContent = `Drawing not saved: ${err.message}`;
  }
}

function unmountBoard() {
  const b = state.board;
  if (!b) return;
  if (b.timer) saveBoard();
  state.board = null;
  b.root.unmount();
  $("#whiteboard").replaceChildren();
}
const MERMAID_SRC = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js";
let mermaidLoad = null;

function isBoard() { return Boolean(state.challenge && state.challenge.type === "whiteboard"); }

function setupBoard(c) {
  const board = c.type === "whiteboard";
  clearInterval(state.timer);
  $("#workspace").classList.toggle("board", board);
  $(".tab-code").textContent = board ? "Design" : "Code";
  $("#run-btn").firstChild.nodeValue = board ? "Check sections " : "Run tests ";
  $("#run-btn").title = board ? "Check which sections are still empty (Ctrl or Cmd + Enter)" : "Run visible tests (Ctrl or Cmd + Enter)";
  $("#submit-btn").hidden = board;
  $("#review-req").replaceChildren(...(board ? [requestButton("grade", `${c.track}/${c.id}`, "Ask for review")] : []));
  $("#hints-intro").textContent = hintsIntro(c.hint_count, board);
  if (board) $("#challenge-meta").append(timerButton(c));
}

// The ladder's rungs, in order (docs/PEDAGOGY.md); a question with fewer hints climbs the first ones.
const RUNGS = ["a question", "the idea", "a next step", "a skeleton"];
const COUNT_WORD = ["No", "One", "Two", "Three", "Four"];
function hintsIntro(n, board) {
  if (!n) return "This question has no hints.";
  const rungs = RUNGS.slice(0, n);
  const ladder = n <= RUNGS.length
    ? `${COUNT_WORD[n]} ${n === 1 ? "rung" : "rungs"}: ${n === 1 ? rungs[0] : `${rungs.slice(0, -1).join(", ")}, then ${rungs[n - 1]}`}.`
    : `${plural(n, "hint")}, each a step closer.`;
  return `${ladder} Each one opens after a ${board ? "section check, so write something" : "test run, so try something"} between hints.`;
}

/** An interview clock: counts down from the question's minutes. It only informs; nothing stops. */
function timerButton(c) {
  const key = `whetstone.timer.${c.track}/${c.id}`;
  const read = () => { try { return Number(localStorage.getItem(key)) || 0; } catch (_) { return 0; } };
  const write = (end) => { try { if (end) localStorage.setItem(key, String(end)); else localStorage.removeItem(key); } catch (_) { /* per-viewer only */ } };
  const btn = el("button", { type: "button", class: "timer", title: "Start or stop the interview clock" });
  const tick = () => {
    const end = read();
    const left = Math.max(0, Math.round((end - Date.now()) / 1000));
    btn.dataset.on = String(Boolean(end));
    btn.textContent = !end ? `Start a ${c.minutes}-minute clock` : left ? `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")} left` : "Time is up";
  };
  btn.addEventListener("click", () => { write(read() ? 0 : Date.now() + c.minutes * 60_000); tick(); });
  state.timer = setInterval(tick, 1000);
  tick();
  return btn;
}

function loadMermaid() {
  mermaidLoad ??= new Promise((resolve) => {
    document.head.append(el("script", { src: MERMAID_SRC, onload: () => resolve(window.mermaid || null), onerror: () => resolve(null) }));
  });
  return mermaidLoad;
}

/** Draw every ```mermaid block in `root`. A broken diagram shows its error instead. */
async function renderMermaid(root) {
  const blocks = $$("code.language-mermaid").filter((c) => root.contains(c));
  if (!blocks.length) return;
  const mermaid = await loadMermaid();
  if (!mermaid) {
    blocks.forEach((c) => c.closest("pre").before(el("p", { class: "diagram-error", text: "Diagrams need the Mermaid script from cdn.jsdelivr.net, which did not load. The text is below." })));
    return;
  }
  // Draw in the app's own colors, so a diagram reads as part of the page in either theme.
  const css = getComputedStyle(document.documentElement);
  const v = (name) => css.getPropertyValue(name).trim();
  mermaid.initialize({
    startOnLoad: false, securityLevel: "strict", theme: "base",
    themeVariables: {
      darkMode: isDark(), fontFamily: "IBM Plex Sans, system-ui, sans-serif", fontSize: "14px",
      background: v("--stone-raised"), primaryColor: v("--stone-sunk"), primaryBorderColor: v("--grit"), primaryTextColor: v("--ink"),
      secondaryColor: v("--stone"), tertiaryColor: v("--stone-raised"), lineColor: v("--grit"), textColor: v("--ink"),
    },
  });
  for (const code of blocks) {
    const pre = code.closest("pre") || code;
    const id = `mmd-${Math.random().toString(36).slice(2)}`;
    try {
      await mermaid.parse(code.textContent);
      const { svg } = await mermaid.render(id, code.textContent);
      const box = el("div", { class: "diagram" });
      box.innerHTML = svg;
      pre.replaceWith(box);
    } catch (err) {
      document.getElementById(`d${id}`)?.remove();  // mermaid leaves its scratch element behind on errors
      pre.before(el("p", { class: "diagram-error", text: `This diagram does not parse: ${String(err.message || err).split("\n").slice(0, 2).join(" ")}` }));
    }
  }
}

async function renderPreview() {
  const box = $("#preview");
  box.replaceChildren(el("p", { class: "results-empty", text: "Drawing the preview…" }));
  try {
    const c = state.challenge;
    if (state.board && state.board.timer) await saveBoard();
    const drawing = await api(`/api/challenges/${c.track}/${c.id}/drawing`);
    // Show the drawing the way the learner's agent reads it, so nothing on the board is a surprise.
    const board = drawing.mermaid
      ? `\n\n## Your whiteboard, as your agent reads it\n\n\`\`\`mermaid\n${drawing.mermaid}\n\`\`\`\n${drawing.notes.map((n) => `\n- Also on the board: ${n}`).join("")}\n`
      : "";
    const { html } = await api("/api/render", { method: "POST", body: { text: getCode() + board } });
    box.innerHTML = html;
    await renderMermaid(box);
    colorize(box);
  } catch (err) {
    box.replaceChildren(el("p", { class: "results-empty", text: `The preview could not be drawn: ${err.message}` }));
  }
}

async function refreshReview() {
  const c = state.challenge;
  const r = await api(`/api/challenges/${c.track}/${c.id}/review`);
  if (state.challenge !== c || !r.review) return;
  const firstSolve = r.solved && !c.solved;
  c.review = r.review;
  if (firstSolve) {
    c.solved = c.solution_open = true;
    updateSolutionGate();
  }
  if (state.lessonLocked) { state.lessonLocked = false; renderLesson(); }
  renderReview(r.review, firstSolve);
  await loadTracks().then(renderRail);
}

const POINT_DOT = { covered: "passed", partial: "partial", missing: "failed" };
const POINT_ORDER = { missing: 0, partial: 1, covered: 2 };

function renderReview(rv, firstSolve) {
  const open = rv.points.filter((p) => p.must && p.verdict !== "covered").length;
  showResults(rv.passed ? "passed" : "failed", rv.passed ? "Passed" : "Not yet", `${rv.covered}/${rv.points.length}`);
  const rows = [...rv.points].sort((a, b) => POINT_ORDER[a.verdict] - POINT_ORDER[b.verdict] || Number(b.must) - Number(a.must));
  $("#results").replaceChildren(
    firstSolve ? el("p", { class: "solved-note", text: "Passed review. A variant of this design comes back in a few days, to make it stick." }) : "",
    el("div", { class: "verdict", "data-status": rv.passed ? "passed" : "failed" },
      el("span", { class: "verdict-word", text: rv.passed ? "Passed review" : "Not yet" }),
      el("span", { class: "verdict-sum", text: `${rv.covered} of ${plural(rv.points.length, "rubric point")} covered. ${open ? `${plural(open, "must-have")} still open.` : "Every must-have is covered."} Reviewed ${shortDate(rv.created_at)}.` })),
    el("p", { class: "review-summary", text: rv.summary }),
    el("ul", { class: "test-list" }, rows.map(reviewRow)));
  $("#results").scrollTop = 0;
}

function reviewRow(p) {
  // A point the design misses stays hidden, like a hidden test: only the agent's question shows.
  const label = p.point || (p.verdict === "partial" ? "Partly covered" : "Not covered yet");
  const name = el("span", { class: "test-name" }, label, p.must ? el("span", { class: "vis", text: "must-have" }) : null);
  const head = [el("span", { class: `dot ${POINT_DOT[p.verdict] || ""}`, "aria-label": p.verdict }), name, el("span", { class: "test-time", text: p.section })];
  return el("li", { class: "test-row" }, el("details", { open: p.verdict !== "covered" },
    el("summary", {}, ...head),
    p.quote ? el("blockquote", { class: "review-quote", text: p.quote }) : null,
    p.note ? el("p", { class: "review-note", text: p.note }) : null));
}

/* ---------- Design: the system design page ---------- */
function initDesign() {
  $("#d-search").addEventListener("input", (e) => { state.designFilter.q = e.target.value.trim().toLowerCase(); renderDesign(); });
  $("#d-company").addEventListener("change", (e) => { state.designFilter.company = e.target.value; renderDesign(); });
  $$("#d-status .chip").forEach((c) => c.addEventListener("click", () => {
    state.designFilter.status = c.dataset.status;
    state.designFilter.chosen = true;
    renderDesign();
  }));
}

async function loadDesign() {
  const [d, profile] = await Promise.all([api("/api/design"), api("/api/profile"), loadTracks()]);
  state.profile = profile;
  state.designs = d.prompts;
  const f = state.designFilter;
  const mine = pathInterests();
  if (!f.chosen) f.status = mine.focus.size || mine.targets.size ? "for-you" : "";
  const counts = new Map();
  for (const p of d.prompts) for (const co of p.companies) counts.set(co, (counts.get(co) || 0) + 1);
  f.company = fillSelect($("#d-company"), "All companies", [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])), f.company);
  const reports = d.prompts.reduce((n, p) => n + p.reports, 0);
  $("#design-lede").textContent = d.prompts.length
    ? `${plural(d.prompts.length, "design question")} from ${plural(reports, "interview report")} at ${plural(counts.size, "company", "companies")}. Write your design on a scratchpad your agent can watch, then ask it to review the design against a rubric.`
    : "No system design questions in the catalog yet.";
  renderDesign();
}

function renderDesign() {
  const f = state.designFilter;
  const mine = pathInterests();
  const forYou = (p) => mine.focus.has(p.id) || p.companies.some((c) => mine.targets.has(c.toLowerCase()));
  const keep = (p) => (!f.company || p.companies.includes(f.company))
    && (!f.status || (f.status === "for-you" ? forYou(p) : f.status === "ready" ? p.questions.length > 0 : !p.questions.length))
    && (!f.q || `${p.title} ${p.summary} ${p.companies.join(" ")} ${p.asked.join(" ")}`.toLowerCase().includes(f.q));
  const rows = state.designs.filter(keep).sort((a, b) => b.reports - a.reports || a.title.localeCompare(b.title));
  $$("#d-status .chip").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.status === f.status)));
  const rank = { attempted: 0, new: 1 };
  const yours = state.designs.flatMap((p) => p.questions.map((q) => ({ ...q, prompt: p.title }))).sort((a, b) => (rank[a.status] ?? 2) - (rank[b.status] ?? 2));
  $("#design-yours").replaceChildren(...(yours.length ? [el("h2", { text: "Your designs" }), el("ul", { class: "home-list" }, yours.map(designQuestionRow))] : []));
  $("#design-count").textContent = rows.length
    ? `Showing ${plural(rows.length, "design question")}, most asked first.${f.status === "for-you" ? " For you means your focus and the companies you target." : ""}`
    : f.status === "for-you" ? "Nothing here for you yet. Choose All, or add skills and companies to your focus." : "Nothing matches. Clear a filter or try another word.";
  const max = Math.max(1, ...rows.map((p) => p.reports));
  $("#design-list").replaceChildren(...rows.map((p) => el("li", {}, designRow(p, max))));
}

const BOARD_STATUS = { new: "Not started", attempted: "In progress", assisted: "Passed with help", solved: "Passed review", mastered: "Mastered" };
function boardAction(q) { return q.status === "new" ? "Start" : q.status === "attempted" ? "Continue" : "Open"; }

function designQuestionRow(q) {
  const review = q.points ? `${q.covered} of ${q.points} rubric points covered` : q.status === "new" ? "" : "Not reviewed yet";
  return el("li", { class: "home-row" },
    el("a", { class: "home-text link-like", href: `#/${q.key}` },
      el("span", { class: "home-title", text: q.title }),
      el("span", { class: "home-sub", text: [q.prompt, BOARD_STATUS[q.status] || q.status, review].filter(Boolean).join(". ") + "." })),
    el("a", { class: `btn ${q.status === "attempted" ? "btn-primary" : "btn-secondary"}`, href: `#/${q.key}` }, boardAction(q)));
}

/** One design question: who asks it and how often. Opening the row shows how it was asked. */
function designRow(p, max) {
  const rowCompanies = p.companies;
  const q = p.questions.find((x) => x.status === "attempted") || p.questions.find((x) => x.status === "new") || p.questions[0];
  const action = q ? el("a", { class: "btn btn-quiet btn-small", href: `#/${q.key}` }, boardAction(q)) : requestButton("design", p.id);
  const asked = p.asked.length ? el("ul", { class: "design-asked", hidden: true }, p.asked.map((t) => el("li", { text: t }))) : null;
  return el("div", { class: "row-item" },
    el("button", { type: "button", class: "row", "aria-expanded": "false", onclick: (e) => {
      if (!asked) return;
      asked.hidden = !asked.hidden;
      e.currentTarget.setAttribute("aria-expanded", String(!asked.hidden));
    } },
      el("span", { class: "row-main" },
        el("span", { class: "row-head" }, el("span", { class: "row-title", text: p.title }), companyStack(rowCompanies)),
        el("span", { class: "row-sub", text: p.asked[0] || p.summary })),
      el("span", { class: "row-asked" },
        el("span", { class: "freq", style: `--w:${Math.round((p.reports / max) * 100)}%`, "aria-hidden": "true" }),
        el("span", {}, el("strong", { text: p.reports }), p.reports === 1 ? " report" : " reports"))),
    el("span", { class: "row-actions" }, action),
    asked);
}

/* ---------- Catalog ---------- */
const ROUNDS = {
  "practical-coding": "Practical coding",
  "system-design": "System design",
  "low-level-design": "Low-level design",
  "concurrency": "Concurrency",
  "debugging": "Debugging",
  "api-integration": "API integration",
  "data-modeling": "Data modeling",
};
const CONFIDENCE = { high: "Well sourced", medium: "One source", low: "Thin source" };

function initCatalog() {
  const chip = (value, label) => el("button", {
    type: "button", class: "chip", "data-round": value, "aria-pressed": value === "" ? "true" : "false",
    onclick: () => {
      state.filters.round = value;
      $$("#f-rounds .chip").forEach((c) => c.setAttribute("aria-pressed", c.dataset.round === value ? "true" : "false"));
      renderCatalog();
    },
  }, label);
  $("#f-rounds").replaceChildren(chip("", "All rounds"), ...Object.entries(ROUNDS).map(([v, l]) => chip(v, l)));
  $("#f-search").addEventListener("input", (e) => { state.filters.q = e.target.value.trim().toLowerCase(); renderCatalog(); });
  $("#f-company").addEventListener("change", (e) => { state.filters.company = e.target.value; renderCatalog(); });
  $$("#f-status .chip").forEach((c) => c.addEventListener("click", () => {
    state.filters.status = c.dataset.status;
    state.filters.statusChosen = true;
    renderCatalog();
  }));
  const dialog = $("#problem-dialog");
  $("#problem-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
}

async function loadCatalog() {
  const [catalog, profile, paths] = await Promise.all([api("/api/catalog"), api("/api/profile"), api("/api/paths")]);
  state.catalog = catalog.problems;
  state.profile = profile;
  state.paths = paths;
  if (!state.filters.statusChosen) state.filters.status = interestSet().size || (profile.targets || []).length ? "for-you" : "";
  const counts = new Map();
  for (const p of state.catalog) for (const r of p.reports) counts.set(r.company, (counts.get(r.company) || 0) + 1);
  const select = $("#f-company");
  const keep = select.value;
  select.replaceChildren(el("option", { value: "", text: "All companies" }),
    ...[...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([c, n]) => el("option", { value: c, text: `${c} (${n})` })));
  const want = (state.filters.company || keep).toLowerCase();
  select.value = [...counts.keys()].find((c) => c.toLowerCase() === want) || "";
  state.filters.company = select.value;
  const reports = state.catalog.reduce((n, p) => n + p.reports.length, 0);
  const asked = state.catalog.filter((p) => p.reports.length).length;
  $("#catalog-lede").textContent = state.catalog.length
    ? `${plural(reports, "interview report")} from ${counts.size} companies, grouped into ${plural(asked, "problem")}. Open one to see what was asked, then practice it with a lesson, an editor and tests.`
    : "No catalog yet. Add content/catalog.yaml (see scripts/merge_catalog.py).";
}

function reportMatches(r) {
  const f = state.filters;
  return (!f.company || r.company === f.company) && (!f.round || r.round === f.round);
}

function searchText(p) {
  p._text ??= [p.title, p.summary, ...p.tags, ...p.companies, ...p.reports.map((r) => r.question)].join(" ").toLowerCase();
  return p._text;
}

function renderCatalog() {
  const f = state.filters;
  const rows = state.catalog
    .map((p) => ({ p, hits: p.reports.filter(reportMatches) }))
    .filter(({ p, hits }) => hits.length && statusMatches(p) && (!f.q || searchText(p).includes(f.q)))
    .sort((a, b) => b.hits.length - a.hits.length || a.p.title.localeCompare(b.p.title));
  $$("#f-status .chip").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.status === f.status)));
  const max = Math.max(1, ...rows.map((r) => r.hits.length));
  const n = rows.reduce((s, r) => s + r.hits.length, 0);
  $("#catalog-count").textContent = rows.length
    ? `Showing ${plural(rows.length, "problem")} and ${plural(n, "report")}, most asked first.${f.status === "for-you" ? " For you means your focus, your paths and the companies you target." : ""}`
    : f.status === "for-you" ? "Nothing here for you yet. Add skills or companies to your focus, or choose All." : "Nothing matches. Clear a filter or try another word.";
  $("#catalog-grid").replaceChildren(...rows.map(({ p, hits }) => el("li", {}, catalogRow(p, hits, max))));
}

function statusMatches(p) {
  const s = state.filters.status;
  if (s === "for-you") return forYou(p);
  return !s || (s === "ready" ? p.links.length > 0 : !p.links.length && p.format !== "design");
}

/** Modules you care about: your focus, and the modules of paths you follow or started. */
function interestSet() {
  const profile = state.profile || {};
  const followed = new Set(profile.paths || []);
  const fromPaths = state.paths.filter((p) => followed.has(p.id) || p.mine).flatMap((p) => p.modules.map((m) => m.module));
  return new Set([...(profile.focus || []), ...fromPaths]);
}

function forYou(p) {
  const targets = ((state.profile && state.profile.targets) || []).map((t) => t.toLowerCase());
  return interestSet().has(p.id) || p.companies.some((c) => targets.includes(c.toLowerCase()));
}

function problemStatus(p) {
  if (!p.links.length) return { kind: "none", text: "Not ready yet" };
  const total = p.links.reduce((s, l) => s + l.total, 0);
  const solved = p.links.reduce((s, l) => s + l.solved, 0);
  return solved
    ? { kind: "progress", text: `${solved} of ${total} solved` }
    : { kind: "ready", text: `${plural(total, "question")} ready` };
}

/** One problem as a compact row: what it is, who asks it, how often, and two actions:
    add it to your focus, and practice it (or ask your agent to build it). */
function catalogRow(p, hits, max) {
  const rowCompanies = [...new Set(hits.map((r) => r.company))].filter((c) => c !== "Unknown");
  const rounds = [...new Set(hits.map((r) => r.round))].map((r) => ROUNDS[r] || r).join(", ");
  const focus = (state.profile && state.profile.focus) || [];
  const inFocus = focus.includes(p.id);
  const link = p.links[0];
  const practice = link ? el("a", { class: "btn btn-quiet btn-small", href: `#/${link.track}/${link.challenge}` }, link.solved ? "Continue" : "Start")
    : requestButton(p.format === "design" ? "design" : "build", p.id);
  return el("div", { class: "row-item" },
    el("button", { type: "button", class: "row", title: rounds, onclick: () => openProblem(p.id) },
      el("span", { class: "row-main" },
        el("span", { class: "row-head" }, el("span", { class: "row-title", text: p.title }), companyStack(rowCompanies)),
        el("span", { class: "row-sub", text: p.summary })),
      el("span", { class: "row-asked" },
        el("span", { class: "freq", style: `--w:${Math.round((hits.length / max) * 100)}%`, "aria-hidden": "true" }),
        el("span", {}, el("strong", { text: hits.length }), hits.length === 1 ? " report" : " reports"))),
    el("span", { class: "row-actions" },
      el("button", { type: "button", class: `btn btn-text btn-small focus-toggle`, "aria-pressed": String(inFocus),
        title: inFocus ? "Remove from your focus" : "Add to your focus",
        onclick: () => saveInterests({ focus: inFocus ? focus.filter((x) => x !== p.id) : [...focus, p.id] }) }, inFocus ? "✓ In focus" : "+ Focus"),
      practice));
}

function safeUrl(u) {
  try {
    const url = new URL(u);
    return url.protocol === "https:" || url.protocol === "http:" ? url : null;
  } catch (_) { return null; }
}

function reportItem(r) {
  const bits = [ROUNDS[r.round] || r.round, r.level, r.year].filter(Boolean).join(", ");
  const links = r.sources.map(safeUrl).filter(Boolean);
  return el("li", { class: "report", "data-match": reportMatches(r) ? "true" : "false" },
    el("p", { class: "report-head" },
      el("strong", { class: "report-co" }, r.company === "Unknown" ? null : companyMark(r.company), r.company),
      el("span", { text: bits }),
      el("span", { class: "conf", "data-c": r.confidence, text: CONFIDENCE[r.confidence] || r.confidence })),
    el("p", { class: "report-q", text: r.question }),
    r.follow_ups.length ? el("ul", { class: "report-follow", "aria-label": "Follow-ups" }, r.follow_ups.map((f) => el("li", { text: f }))) : null,
    links.length ? el("p", { class: "report-src" }, "Sources: ", ...sourceLinks(links)) : null);
}

/** "prachub.com 1 2 3, 1point3acres.com": one name per site, with numbered links when it repeats. */
function sourceLinks(links) {
  const byHost = new Map();
  for (const u of links) {
    const host = u.hostname.replace(/^www\./, "");
    byHost.set(host, [...(byHost.get(host) || []), u]);
  }
  const a = (u, text) => el("a", { href: u.href, target: "_blank", rel: "noopener noreferrer", text });
  return [...byHost].flatMap(([host, urls], i) => [i ? ", " : null,
    urls.length === 1 ? a(urls[0], host) : el("span", {}, `${host} `, ...urls.flatMap((u, n) => [n ? " " : null, a(u, String(n + 1))]))]);
}

function openProblem(id) {
  const p = state.catalog.find((x) => x.id === id);
  if (!p) return;
  $("#problem-title").textContent = p.title;
  $("#problem-summary").textContent = p.summary;
  const nCo = p.companies.length;
  const rounds = p.rounds.map((r) => ROUNDS[r] || r).join(", ");
  $("#problem-meta").textContent = `${plural(p.reports.length, "report")} from ${nCo} ${nCo === 1 ? "company" : "companies"}. Rounds: ${rounds}.`;
  renderProblemActions(p);
  $("#problem-log").hidden = true;
  // Reports matching the current filters come first; the YAML already orders by confidence, then year.
  const sorted = [...p.reports].sort((a, b) => Number(reportMatches(b)) - Number(reportMatches(a)));
  $("#problem-reports").replaceChildren(...sorted.map(reportItem));
  $("#problem-dialog").showModal();
  $("#problem-dialog .drawer-inner").scrollTop = 0;
}

function renderProblemActions(p) {
  const close = () => $("#problem-dialog").close();
  const nodes = p.links.map((l, i) => el("a", {
    class: `btn ${i ? "btn-secondary" : "btn-primary"}`, href: `#/${l.track}/${l.challenge}`, onclick: close,
  }, l.solved ? `Continue: ${l.title} (${l.solved} of ${l.total} solved)` : `Start: ${l.title}`));
  const own = p.links.some((l) => l.own);
  if (p.format === "design") {
    nodes.push(el("div", { class: "agent-ask" },
      el("p", { class: "note", text: "This is a system design round. Your agent prepares a design question: you write the design on a scratchpad it can watch, and it reviews the design against a rubric." }),
      requestButton("design", p.id, "Prepare a design question")));
  } else if (state.config && state.config.generator_enabled) {
    nodes.push(el("button", {
      type: "button", class: `btn ${p.links.length ? "btn-quiet" : "btn-primary"}`, id: "build-btn", onclick: () => buildProblem(p),
    }, `Prepare ${own ? "the next" : "a"} question`));
  } else {
    nodes.push(el("div", { class: "agent-ask" },
      el("p", { class: "note", text: `Your agent writes ${own ? "the next" : "a"} question for you on your own AI subscription, and Whetstone checks it before it appears here.` }),
      requestButton("build", p.id, own ? "Prepare the next question" : "Prepare a question")));
  }
  $("#problem-actions").replaceChildren(...nodes);
}

async function copyText(text, btn) {
  try {
    await navigator.clipboard.writeText(text);
    btn.textContent = "Copied";
  } catch (_) {
    btn.textContent = "Select the text to copy";
  }
  setTimeout(() => { btn.textContent = "Copy request"; }, 1600);
}

async function buildProblem(p) {
  const btn = $("#build-btn"), log = $("#problem-log");
  btn.disabled = true;
  btn.textContent = "Claude is writing and Whetstone is checking. About a minute…";
  log.hidden = true;
  const retry = () => { btn.disabled = false; btn.textContent = "Try again"; };
  try {
    const res = await api(`/api/catalog/${encodeURIComponent(p.id)}/build`, { method: "POST" });
    log.textContent = res.log.join("\n") + (res.ok ? "" : `\n\n${res.error}`);
    log.hidden = false;
    if (!res.ok) return retry();
    await loadTracks();
    $("#problem-dialog").close();
    location.hash = `#/${res.track}/${res.id}`;
  } catch (err) {
    log.textContent = err.message;
    log.hidden = false;
    retry();
  }
}

/* ---------- Paths ---------- */
// A path is a system to build (a payment processor, a taxi service, an LLM gateway), made of
// modules in order. Modules that are not built yet are placeholders the learner's agent fills in.
// The filters live in the URL (#/paths?company=Stripe&module=ledger), so reload and Back keep them.
const PATH_FILTERS = ["q", "foryou", "ready", "domain", "company", "module", "sort"];
const PATH_SORTS = { match: "best match first", asked: "most asked first", ready: "readiest first", az: "A to Z" };
const STOP_TEXT = { done: "solved", built: "ready to practice", none: "your agent prepares it" };

function initPaths() {
  $("#p-search").addEventListener("input", (e) => setPathFilter({ q: e.target.value.trim() }));
  $("#p-sort").addEventListener("change", (e) => setPathFilter({ sort: e.target.value }));
  $("#p-domain").addEventListener("change", (e) => setPathFilter({ domain: e.target.value }));
  $("#p-company").addEventListener("change", (e) => setPathFilter({ company: e.target.value }));
  $("#p-foryou").addEventListener("click", () => setPathFilter({ foryou: !state.pathFilter.foryou }));
  $("#p-ready").addEventListener("click", () => setPathFilter({ ready: !state.pathFilter.ready }));
  $("#p-clear").addEventListener("click", () => setPathFilter({ q: "", foryou: false, ready: false, domain: "", company: "", module: "" }));
  const dialog = $("#path-dialog");
  $("#path-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
}

function readPathFilter() {
  const q = new URLSearchParams(location.hash.split("?")[1] || "");
  state.pathFilter = {
    q: q.get("q") || "", foryou: q.has("foryou"), ready: q.has("ready"),
    domain: q.get("domain") || "", company: q.get("company") || "", module: q.get("module") || "", sort: q.get("sort") || "",
  };
}

// replaceState, not a hash change: a filter must not reload the page or add a history step per keystroke.
function setPathFilter(patch) {
  Object.assign(state.pathFilter, patch);
  const q = new URLSearchParams();
  for (const k of PATH_FILTERS) {
    const v = state.pathFilter[k];
    if (v) q.set(k, v === true ? "1" : v);
  }
  const query = q.toString();
  history.replaceState(null, "", `#/paths${query ? `?${query}` : ""}`);
  renderPaths();
}

async function loadPaths() {
  // Reload modules too, so a module the agent just built links straight into Practice.
  const [paths, profile] = await Promise.all([api("/api/paths"), api("/api/profile"), loadTracks()]);
  state.profile = profile;
  state.paths = paths;
  readPathFilter();
  const f = state.pathFilter;
  const tally = (values) => {
    const counts = new Map();
    for (const v of values) counts.set(v, (counts.get(v) || 0) + 1);
    return [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  };
  const companies = tally(paths.flatMap((p) => p.companies));
  f.domain = fillSelect($("#p-domain"), "All domains", tally(paths.map((p) => p.domain || "Other")).sort((a, b) => a[0].localeCompare(b[0])), f.domain);
  f.company = fillSelect($("#p-company"), "All companies", companies, f.company);
  $("#p-search").value = f.q;
  $("#paths-lede").textContent = paths.length
    ? `${plural(paths.length, "system")} to build${companies.length ? `, modelled on ${plural(companies.length, "company", "companies")}` : ""}. Pick one you want to understand.`
    : "No learning paths yet.";
  renderPaths();
}

/** Fills a filter dropdown with "value (count)" options and returns the value it kept. */
function fillSelect(select, all, counts, value) {
  select.replaceChildren(el("option", { value: "", text: all }), ...counts.map(([v, n]) => el("option", { value: v, text: `${v} (${n})` })));
  select.value = counts.some(([v]) => v === value) ? value : "";
  return select.value;
}

// A module grows one question at a time, up to `planned` (the steps of catalog.RECIPE).
const moreToCome = (m) => m.questions < m.planned;
const moduleDone = (m) => m.built && m.solved === m.questions && !moreToCome(m);

function pathStats(p) {
  const built = p.modules.filter((m) => m.built);
  return {
    built: built.length,
    done: built.filter(moduleDone).length,
    total: built.reduce((s, m) => s + m.questions, 0),
    solved: built.reduce((s, m) => s + m.solved, 0),
    reports: p.modules.reduce((s, m) => s + m.reports, 0),
  };
}

function pathText(p) {
  p._text ??= [p.title, p.goal, p.domain, ...p.companies, ...p.modules.map((m) => `${m.title} ${m.summary || ""}`)].join(" ").toLowerCase();
  return p._text;
}

/** Your focus modules and target companies, from the profile. */
function pathInterests() {
  const profile = state.profile || {};
  return { focus: new Set(profile.focus || []), targets: new Set((profile.targets || []).map((t) => t.toLowerCase())) };
}

/** Why a path suits you: the focus modules it uses and the target companies it names. */
function pathMatch(p, mine) {
  const focus = p.modules.filter((m) => mine.focus.has(m.module));
  const targets = p.companies.filter((c) => mine.targets.has(c.toLowerCase()));
  return { focus, targets, score: focus.length * 2 + (targets.length ? 1 : 0) };
}

/** The title without the "Build a" that nearly every path starts with. */
function shortTitle(p) {
  const t = p.title.replace(/^build (an?|the) /i, "");
  return t.charAt(0).toUpperCase() + t.slice(1);
}

function renderPaths() {
  const f = state.pathFilter;
  const mine = pathInterests();
  const personal = mine.focus.size > 0 || mine.targets.size > 0;
  const sort = PATH_SORTS[f.sort] && (f.sort !== "match" || personal) ? f.sort : personal ? "match" : "ready";
  const filtering = Boolean(f.q || f.foryou || f.ready || f.domain || f.company || f.module);
  const followed = new Set((state.profile && state.profile.paths) || []);
  const q = f.q.toLowerCase();
  const all = state.paths.map((p) => ({ p, st: pathStats(p), match: pathMatch(p, mine) }));
  const started = ({ p, st }) => p.mine || followed.has(p.id) || st.solved > 0;
  const keep = ({ p, st, match }) => (!f.foryou || match.score > 0) && (!f.ready || st.built > 0)
    && (!f.domain || (p.domain || "Other") === f.domain) && (!f.company || p.companies.includes(f.company))
    && (!f.module || p.modules.some((m) => m.module === f.module)) && (!q || pathText(p).includes(q));
  const order = {
    match: (x, y) => y.match.score - x.match.score || y.st.built - x.st.built || y.st.reports - x.st.reports,
    asked: (x, y) => y.st.reports - x.st.reports,
    ready: (x, y) => y.st.built - x.st.built || y.st.reports - x.st.reports,
    az: () => 0,
  }[sort];
  // Your paths sit in their own list above the grid, unless a filter is on.
  const yours = filtering ? [] : all.filter(started).map((r) => r.p);
  const rows = all.filter((r) => (filtering || !started(r)) && keep(r))
    .sort((x, y) => order(x, y) || shortTitle(x.p).localeCompare(shortTitle(y.p)));

  $("#p-foryou").hidden = !personal;
  $("#p-sort option[value='match']").hidden = !personal;
  $("#p-sort").value = sort;
  $("#p-foryou").setAttribute("aria-pressed", String(f.foryou));
  $("#p-ready").setAttribute("aria-pressed", String(f.ready));
  $("#p-foryou").textContent = `For you (${all.filter((r) => r.match.score).length})`;
  $("#p-ready").textContent = `Ready now (${all.filter((r) => r.st.built).length})`;
  for (const [id, v] of [["#p-domain", f.domain], ["#p-company", f.company]]) {
    $(id).value = v;
    $(id).dataset.on = String(Boolean(v));
  }
  const used = f.module && state.paths.flatMap((p) => p.modules).find((m) => m.module === f.module);
  $("#p-module").replaceChildren(...(f.module ? [el("span", { class: "chip-tag chip-on" }, `Uses ${used ? used.title : f.module}`,
    el("button", { type: "button", class: "chip-x", "aria-label": "Stop filtering by this module", onclick: () => setPathFilter({ module: "" }) }, "×"))] : []));
  $("#p-clear").hidden = !filtering;

  $("#paths-yours").replaceChildren(...(yours.length ? [el("h2", { text: "Your paths" }), el("ul", { class: "home-list" }, yours.map(yourPathRow))] : []));
  $("#paths-count").textContent = rows.length
    ? `${filtering ? "Showing " : ""}${plural(rows.length, yours.length ? "more path" : "path")}, ${PATH_SORTS[sort]}.`
    : "";
  $("#paths-legend").replaceChildren(...(rows.length || yours.length ? routeLegend(mine.focus.size > 0) : []));
  $("#paths-list").replaceChildren(...(rows.length ? rows.map(({ p, st }) => el("li", {}, pathTile(p, st))) : [el("li", { class: "agent-ask" },
    el("p", { class: "note", text: state.paths.length ? "Nothing matches. Clear a filter, or ask your agent for a new path:" : "No learning paths yet. Open this folder in Claude Code, Codex, Cursor or another coding agent and ask:" }),
    el("p", { class: "ask-line" }, el("code", { text: "Make me a Whetstone learning path to build …" })))]));
}

function moduleState(m) {
  return !m.built ? "none" : moduleDone(m) ? "done" : "built";
}

/** A path as a line of stops, one per module: solved, ready, or for your agent to build. Your focus
    modules carry a clay pip. On a card, each stop is a button that shows every path using its module. */
function routeMap(p, interactive) {
  const focus = pathInterests().focus;
  return el("span", { class: "route-map", ...(interactive ? { role: "group", "aria-label": "Modules" } : { "aria-hidden": "true" }) },
    p.modules.map((m) => {
      const s = moduleState(m);
      const attrs = { class: "stop", "data-s": s, "data-focus": focus.has(m.module) ? "" : null };
      let stop;
      if (!interactive) {
        stop = el("span", attrs);
        stop.stopInfo = m;  // read by the stop popover
        return stop;
      }
      const on = state.pathFilter.module === m.module;
      stop = el("button", {
        type: "button", ...attrs, "data-module": m.module, "aria-pressed": String(on),
        "aria-label": `${m.title}, ${STOP_TEXT[s]}. Show every path that uses it.`,
        onclick: () => {
          setPathFilter({ module: on ? "" : m.module });
          const again = $(`#paths-list [data-path="${p.id}"] .stop[data-module="${m.module}"]`);
          if (again) again.focus();
        },
      });
      stop.stopInfo = m;
      return stop;
    }));
}

/* A popover for route stops: the module, where you are with it, and what it covers. It opens
   quickly on hover or keyboard focus, and never takes the pointer. */
function stopLine(m, s) {
  if (s === "none") return `Your agent prepares it${m.reports ? `. Seen in ${plural(m.reports, "interview report")}` : ""}.`;
  if (s === "done") return `Solved, all ${plural(m.questions, "question")}.`;
  return moreToCome(m) ? `${m.questions} of ${m.planned} questions ready, ${m.solved} solved.` : `${m.solved} of ${plural(m.questions, "question")} solved.`;
}

function initStopTips() {
  const tip = $("#stop-tip");
  let timer = 0;
  const show = (stop) => {
    const m = stop.stopInfo;
    tip.replaceChildren(
      el("p", { class: "stop-tip-title" }, el("span", { class: "stop", "data-s": stop.dataset.s }), m.title,
        stop.hasAttribute("data-focus") ? el("span", { class: "tag-focus", text: "Your focus" }) : null),
      el("p", { class: "stop-tip-line", text: stopLine(m, stop.dataset.s) }),
      m.summary ? el("p", { class: "stop-tip-what", text: m.summary }) : null,
      stop.tagName === "BUTTON" ? el("p", { class: "stop-tip-hint", text: "Click to see every path that uses it." }) : null);
    if (!tip.matches(":popover-open")) tip.showPopover();
    const r = stop.getBoundingClientRect();
    const w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = `${Math.max(8, Math.min(innerWidth - w - 8, r.left + r.width / 2 - w / 2))}px`;
    tip.style.top = `${r.top - h - 8 >= 8 ? r.top - h - 8 : r.bottom + 8}px`;
  };
  const hide = () => {
    clearTimeout(timer);
    if (tip.matches(":popover-open")) tip.hidePopover();
  };
  document.addEventListener("pointerover", (e) => {
    const stop = e.target.closest && e.target.closest(".stop");
    if (!stop || !stop.stopInfo) return;
    clearTimeout(timer);
    timer = setTimeout(() => show(stop), 60);
  });
  document.addEventListener("pointerout", (e) => {
    const next = e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest(".stop");
    if (e.target.closest && e.target.closest(".stop") && !(next && next.stopInfo)) hide();  // stop to stop: just move
  });
  document.addEventListener("focusin", (e) => (e.target.stopInfo ? show(e.target) : hide()));
  document.addEventListener("scroll", hide, true);
}

function routeLegend(focus) {
  const item = (s, text) => el("span", { class: "legend-item" }, el("span", { class: "stop", "data-s": s }), text);
  return [item("done", "solved"), item("built", "ready"), item("none", "your agent prepares it"),
    focus ? el("span", { class: "legend-item" }, el("span", { class: "pip" }), "your focus") : null,
    el("span", { text: "Pick a stop to see every path that uses its module." })];
}

/** What you can do with a path now: modules solved, ready to practice, and still to build. */
function pathSummary(p, st) {
  const ready = st.built - st.done;
  const none = p.modules.length - st.built;
  const parts = [st.done && `${st.done} solved`, ready && `${ready} ready`, none && `${none} for your agent`].filter(Boolean);
  return parts.length ? `Modules: ${parts.join(", ")}` : "No modules yet";
}

function yourPathRow(p) {
  const m = p.modules.find((x) => !x.built || x.solved < x.questions);
  const action = !m ? el("button", { type: "button", class: "btn btn-quiet", onclick: () => openPath(p.id) }, "Review")
    : m.built ? el("a", { class: "btn btn-secondary", href: `#/${m.module}/${m.next}` }, m.solved ? `Continue: ${m.title}` : `Start: ${m.title}`)
      : requestButton("build", m.module, `Prepare: ${m.title}`);
  return el("li", { class: "home-row" },
    el("button", { type: "button", class: "home-text link-like", onclick: () => openPath(p.id) },
      el("span", { class: "home-title" }, domainTile(p.domain, true), p.title),
      routeMap(p, false)),
    action);
}

/** A path on the grid. The title button opens it, and its click area covers the card; the stops
    sit above that area so each one can filter by its module. */
function pathTile(p, st) {
  return el("article", { class: "card path-tile", "data-path": p.id },
    el("div", { class: "tile-head" }, domainTile(p.domain),
      el("h3", { class: "card-title" },
        el("button", { type: "button", class: "path-open", onclick: () => openPath(p.id) }, shortTitle(p)),
        p.mine ? el("span", { class: "tag-mine", text: "Yours" }) : null),
      companyStack(p.companies, 4)),
    p.goal ? el("p", { class: "card-summary path-goal-short", text: p.goal }) : null,
    routeMap(p, true),
    el("p", { class: "card-foot" }, el("span", { class: "card-rounds", text: plural(st.reports, "interview report") })));
}

function openPath(id) {
  const p = state.paths.find((x) => x.id === id);
  if (!p) return;
  $("#path-detail").replaceChildren(pathCard(p));
  $("#path-dialog").dataset.path = id;
  $("#path-dialog").showModal();
  $("#path-dialog .drawer-inner").scrollTop = 0;
}

/** How many paths use each module. */
function moduleUse() {
  const uses = new Map();
  for (const p of state.paths) for (const m of new Set(p.modules.map((x) => x.module))) uses.set(m, (uses.get(m) || 0) + 1);
  return uses;
}

/** From the drawer: every path that uses a module, with the other filters cleared. */
function showPathsUsing(module) {
  $("#path-dialog").close();
  if ($("#paths").hidden) {
    location.hash = `#/paths?module=${encodeURIComponent(module)}`;
    return;
  }
  setPathFilter({ q: "", foryou: false, ready: false, domain: "", company: "", module });
  $(".path-filters").scrollIntoView({ block: "start" });
}

function pathCard(p) {
  const st = pathStats(p);
  const current = p.modules.findIndex((m) => m.built && m.solved < m.questions);
  const focus = pathInterests().focus;
  const uses = moduleUse();
  return el("section", { class: "path", "aria-labelledby": `path-${p.id}` },
    el("span", { class: "wear", style: `--w:${st.total ? Math.round((st.solved / st.total) * 100) : 0}%`, "aria-hidden": "true" }),
    p.domain ? el("p", { class: "path-domain" }, domainTile(p.domain, true), p.domain) : null,
    p.companies.length ? el("ul", { class: "path-companies", "aria-label": "Modelled on" },
      p.companies.map((c) => el("li", {}, companyMark(c), c))) : null,
    el("div", { class: "path-head" }, el("h2", { id: `path-${p.id}`, text: p.title }), followButton(p)),
    p.goal ? el("p", { class: "path-goal", text: p.goal }) : null,
    el("p", { class: "path-sum", text: `${pathSummary(p, st)}.${st.total ? ` ${st.solved} of ${plural(st.total, "question")} solved.` : ""}` }),
    p.modules.some((m) => !m.built) ? el("div", { class: "agent-ask fill-ask" },
      el("p", { class: "note", text: `${plural(p.modules.filter((m) => !m.built).length, "module")} not ready yet. Your agent prepares the first question of each, in order, so you can start the first while it works on the rest:` }),
      requestButton("fill-path", p.id)) : null,
    p.modules.length
      ? el("ol", { class: "path-line" }, p.modules.map((m, i) => moduleStep(m, i, i === current, focus.has(m.module), (uses.get(m.module) || 1) - 1)))
      : el("p", { class: "path-sum" }, "No modules yet. Ask your agent to add some, or run ", el("code", { text: `bin/whetstone path add ${p.id} <module>` })));
}

function followButton(p) {
  const followed = ((state.profile && state.profile.paths) || []).includes(p.id);
  return el("button", { type: "button", class: `btn ${followed ? "btn-quiet" : "btn-secondary"} btn-small follow`, "aria-pressed": String(followed),
    onclick: async () => {
      const paths = (state.profile && state.profile.paths) || [];
      await saveInterests({ paths: followed ? paths.filter((x) => x !== p.id) : [...paths, p.id] });
      $("#path-detail").replaceChildren(pathCard(p));
    } }, followed ? "Following ✓" : "Follow this path");
}

function moduleStep(m, i, isCurrent, inFocus, others) {
  const kind = !m.built ? "none" : moduleDone(m) ? "done" : m.solved ? "progress" : "ready";
  let action;
  if (m.built && m.solved === m.questions && moreToCome(m)) {
    action = requestButton("build", m.module, "Prepare the next question");
  } else if (m.built) {
    action = el("a", { class: `btn ${isCurrent ? "btn-primary" : "btn-secondary"}`, href: `#/${m.module}/${m.next}`, onclick: () => $("#path-dialog").close() },
      { ready: "Start", progress: "Continue", done: "Review" }[kind]);
  } else {
    action = requestButton("build", m.module);
  }
  const sub = m.built
    ? moreToCome(m)
      ? `${m.questions} of ${m.planned} questions ready, ${m.solved} solved.`
      : `${m.solved} of ${plural(m.questions, "question")} solved`
    : `Not ready yet${m.reports ? `. Seen in ${plural(m.reports, "interview report")}` : ""}.`;
  return el("li", { class: "path-step", "data-s": kind, "aria-current": isCurrent ? "step" : null },
    el("span", { class: "notch", "aria-hidden": "true" }, kind === "done" ? "✓" : String(i + 1)),
    el("div", { class: "path-step-body" },
      el("div", { class: "path-step-text" },
        el("span", { class: "path-step-title" }, m.title, inFocus ? el("span", { class: "tag-focus", text: "Your focus" }) : null),
        m.summary ? el("span", { class: "path-step-what", text: m.summary }) : null,
        el("span", { class: "path-step-sub", text: sub }),
        others ? el("button", { type: "button", class: "also-in", onclick: () => showPathsUsing(m.module) }, `Also in ${plural(others, "other path")}`) : null),
      action));
}


/* ---------- Practice home: the personal dashboard ---------- */
// Who you are, how sharp each skill is, what to do next, honest numbers, and a game layer that
// rewards mastery, never volume (docs/PEDAGOGY.md, rule 12).
const GAME_KEY = "whetstone.game";
function gameOn() { try { return localStorage.getItem(GAME_KEY) !== "off"; } catch (_) { return true; } }
function setGame(on) { try { localStorage.setItem(GAME_KEY, on ? "on" : "off"); } catch (_) { /* per-viewer only */ } }

async function loadHome() {
  const [d, paths] = await Promise.all([api("/api/dashboard"), api("/api/paths"), loadTracks()]);
  state.paths = paths;
  state.dash = d;
  state.profile = d.profile;
  renderHome();
}

function renderHome() {
  const progress = location.hash.startsWith("#/progress");
  const d = state.dash;
  // Today leads with the next step; the profile header lives on the Progress page.
  $("#home-title").textContent = progress ? d.profile.name || "Your progress" : "Today";
  const lede = [d.profile.role, d.profile.goal ? `Goal: ${d.profile.goal}` : ""].filter(Boolean).map((t) => t.replace(/\.$/, "")).join(". ");
  $("#home-lede").textContent = progress && lede ? `${lede}.` : weekLine(d.week);
  $("#home-body").classList.toggle("today-grid", !progress);
  $("#home-body").replaceChildren(...(progress ? progressSections(d) : todaySections(d, state.paths)));
}

/* ---------- Today: the next step first, then your focus; the week and the log beside it when wide ---------- */
function todaySections(d, paths) {
  const picks = todayPicks(d, paths);
  const main = el("div", { class: "today-main" });
  main.append(el("section", { class: "today-block", "aria-label": "Today" },
    picks.length ? todayCard(picks[0]) : null,
    picks[1] ? todayAlt(picks[1]) : null,
    reviewLine(d)));
  const setup = setupSection(setupSteps(d, paths), d);
  if (setup) main.append(setup);
  main.append(homeSection("Your focus", focusSection(d), el("p", { class: "home-sub section-note", text: "The skills, companies and paths you want to keep sharp. Your agent reads this list too." })));
  main.append(profileLine(d.profile));
  const side = el("aside", { class: "today-side", "aria-label": "This week" },
    homeSection("Practice days", calendar(d.active_days)),
    d.recent.length ? homeSection("Recent", el("ol", { class: "log" }, d.recent.map(logLine))) : null);
  return [main, side];
}

/** The one card: what to do now, where it sits in its module, and the clay button. */
function todayCard(pk) {
  const [moduleId, qid] = (pk.key || "").split("/");
  const t = state.tracks.find((x) => x.id === moduleId);
  const i = t ? t.challenges.findIndex((c) => c.id === qid) : -1;
  const eyebrow = i >= 0 ? `${pk.kind} in ${t.title}, question ${i + 1} of ${t.challenges.length}` : pk.kind;
  return el("div", { class: "today-card" },
    el("p", { class: "today-kind" }, icon(PICK_ICON[pk.kind] || "compass"), eyebrow),
    el("h2", { class: "today-title", text: pk.title }),
    el("p", { class: "home-sub", text: pk.why }),
    t ? moduleStrip(t, i) : null,
    el("div", { class: "today-action" }, pk.action));
}

/** The module as a line of stops, one per question; the current one is ringed. */
function moduleStrip(t, current) {
  const done = new Set(["solved", "assisted", "mastered"]);
  return el("span", { class: "route-map module-strip", role: "img", "aria-label": `${t.title}: question ${current + 1} of ${t.challenges.length}` },
    t.challenges.map((c, i) => el("span", { class: "stop", "data-s": done.has(c.status) ? "done" : "built", "aria-current": i === current ? "step" : null, title: c.title })));
}

/** The second choice as a line of text, so the card keeps the only button. */
function todayAlt(pk) {
  const kind = pk.kind === "Next in your path" ? "next in your path" : pk.kind.toLowerCase();
  return el("p", { class: "today-alt home-sub" }, `Or ${kind}: `,
    pk.key ? el("a", { href: `#/${pk.key}`, text: pk.title }) : el("span", { text: pk.title }),
    pk.kind === "Next in your path" ? ` · ${pk.why}` : "",
    pk.key ? null : el("span", { class: "today-alt-req" }, pk.action));
}

/** Reviews due today, or when the next one lands. */
function reviewLine(d) {
  const today = isoDay(new Date());
  const due = d.questions.filter((r) => r.review_due && r.review_due <= today).length;
  const next = d.questions.map((r) => r.review_due).filter((x) => x && x > today).sort()[0];
  const text = due ? `${plural(due, "review")} due today.`
    : next ? `No reviews due. The next lands ${shortDate(next)}.`
      : "No reviews due. The first lands 3 days after your first solve on your own.";
  return el("p", { class: "review-line home-sub" }, icon("rotate-ccw"), text);
}

/** Who you are, in one line. The full header is on the Progress page. */
function profileLine(p) {
  const stack = p.stack || [];
  const bits = [p.name, p.role, stack.length ? stack.slice(0, 5).join(", ") + (stack.length > 5 ? ` and ${stack.length - 5} more` : "") : null].filter(Boolean);
  return el("a", { class: "profile-line", href: "#/progress" }, ...bits.map((b) => el("span", { text: b })), el("span", { class: "profile-line-go", text: "Your progress" }));
}

/** Up to two next steps, most useful first: a due review, the question in progress,
    the next step in a path you follow, then something new in your focus. `key` names the
    question when there is one to open. */
function todayPicks(d, paths) {
  const q = d.questions;
  const today = isoDay(new Date());
  const start = (r, verb) => el("a", { class: "btn btn-primary", href: `#/${r.key}` }, verb);
  const picks = [];
  for (const r of q.filter((x) => x.review_due && x.review_due <= today)) {
    const variant = q.find((x) => x.variant_of === r.key && x.status !== "solved");
    picks.push({ kind: "Review", title: variant ? variant.title : r.title, target: r.key, key: variant ? variant.key : null,
      why: `Solved on ${shortDate(r.solved_at)}. A fresh variant checks that it stuck.`,
      action: variant ? start(variant, "Start review") : requestButton("variant", r.key, "Prepare review variant") });
  }
  const open = q.filter((r) => r.status === "attempted").sort((a, b) => b.last_run.created_at.localeCompare(a.last_run.created_at));
  for (const r of open.slice(0, 2)) {
    picks.push({ kind: "Continue", title: r.title, target: r.key, key: r.key,
      why: `Last run ${shortDate(r.last_run.created_at)}: ${r.last_run.passed} of ${r.last_run.total} tests passed.`, action: start(r, "Continue") });
  }
  const followed = new Set(d.profile.paths || []);
  for (const p of paths.filter((x) => followed.has(x.id) || x.mine || pathStats(x).solved)) {
    const m = p.modules.find((x) => !x.built || x.solved < x.questions);
    if (!m) continue;
    picks.push({ kind: "Next in your path", title: m.title, target: m.module, key: m.built ? `${m.module}/${m.next}` : null, why: p.title,
      action: m.built ? el("a", { class: "btn btn-primary", href: `#/${m.module}/${m.next}` }, "Start") : requestButton("build", m.module) });
  }
  for (const e of d.edges.filter((x) => x.focus && !x.built)) {
    picks.push({ kind: "From your focus", title: e.title, target: e.module, key: null, why: "Not ready yet. Your agent prepares the first question.", action: requestButton("build", e.module) });
  }
  const fresh = q.find((r) => r.status === "new");
  if (fresh) picks.push({ kind: "Start something new", title: fresh.title, target: fresh.key, key: fresh.key, why: `Not started. ${moduleName(fresh.module)}.`, action: start(fresh, "Start") });
  const seen = new Set();
  return picks.filter((pk) => !seen.has(pk.target) && seen.add(pk.target)).slice(0, 2);
}

const PICK_ICON = { Review: "rotate-ccw", Continue: "play", "Next in your path": "route", "From your focus": "crosshair", "Start something new": "compass" };

function moduleName(id) { return (state.tracks.find((t) => t.id === id) || { title: id }).title; }

/** Your focus: each skill's edge, plus the companies and paths you follow. All editable. */
function focusSection(d) {
  const profile = d.profile;
  const box = el("div", { class: "focus" });
  // Rows, with blades, only for the skills you chose or have practiced, the most urgent first.
  // Every other module that is ready sits in one compact row below, so the list stays short.
  const today = isoDay(new Date());
  const mine = d.edges.filter((e) => e.focus || e.state).sort((a, b) => edgeRank(a, today) - edgeRank(b, today));
  const rest = d.edges.filter((e) => !e.focus && !e.state);
  const more = (n, open, onclick) => el("button", { type: "button", class: "btn btn-text btn-small more-btn", onclick },
    open ? "Show fewer" : `Show all ${n}`);
  box.append(mine.length ? edgeList(state.focusOpen ? mine : mine.slice(0, FOCUS_ROWS), gameOn(), d)
    : el("p", { class: "home-sub", text: "Nothing in your focus yet. Add a skill below, or pick one that is ready." }));
  if (mine.length > FOCUS_ROWS) box.append(more(mine.length, state.focusOpen, () => { state.focusOpen = !state.focusOpen; renderHome(); }));
  if (rest.length) box.append(readyRow(rest, d, more));
  box.append(addRow("Add a skill", "module-options", "Rate limiter, Job scheduler…", async (value) => {
    const p = await findModule(value);
    if (!p) return "Pick a skill from the list.";
    await saveInterests({ focus: [...(profile.focus || []), p.id] });
  }));
  box.append(chipList("Companies", profile.targets || [], (c) => saveInterests({ targets: profile.targets.filter((x) => x !== c) }), null, companyMark));
  box.append(addRow("Add a company", "company-options", "Stripe, Netflix…", async (value) => {
    await saveInterests({ targets: [...(profile.targets || []), value] });
  }));
  const followed = (profile.paths || []).map((id) => state.paths.find((p) => p.id === id)).filter(Boolean);
  box.append(chipList("Paths you follow", followed.map((p) => p.title), (title) => {
    const p = followed.find((x) => x.title === title);
    return saveInterests({ paths: profile.paths.filter((x) => x !== p.id) });
  }, el("a", { class: "btn btn-text btn-small", href: "#/paths" }, "Browse paths")));
  fillOptions();
  return box;
}

const FOCUS_ROWS = 6;
const READY_CHIPS = 8;
const LABEL_RANK = { dull: 1, dulling: 2, holding: 3, sharp: 4, "not started": 5 };
/** What needs you first: a review due, then the dullest practiced skill, then skills you chose but have not started. */
function edgeRank(e, today) {
  if (!e.built) return 6;
  if (e.review_due && e.review_due <= today) return 0;
  return LABEL_RANK[e.label] ?? 5;
}

/** Modules that are ready but not in your focus, as a row of chips that open their first question. */
function readyRow(edges, d, more) {
  const chip = (e) => {
    const next = d.questions.find((r) => r.module === e.module && r.status !== "solved");
    return next ? el("a", { class: "chip-tag chip-link", href: `#/${next.key}`, title: `Start ${e.title}` }, e.title)
      : requestButton("build", e.module, `Prepare ${e.title}`);
  };
  const shown = state.readyOpen ? edges : edges.slice(0, READY_CHIPS);
  return el("div", { class: "chip-row ready-row" }, el("span", { class: "chip-row-label", text: "Ready to start" }),
    ...shown.map(chip),
    edges.length > READY_CHIPS ? more(edges.length, state.readyOpen, () => { state.readyOpen = !state.readyOpen; renderHome(); }) : null);
}

function chipList(label, items, onRemove, extra, mark) {
  return el("div", { class: "chip-row" }, el("span", { class: "chip-row-label", text: label }),
    ...(items.length ? items.map((item) => el("span", { class: "chip-tag" }, mark ? mark(item) : null, item,
      el("button", { type: "button", class: "chip-x", "aria-label": `Remove ${item}`, onclick: () => onRemove(item) }, "×"))) : [el("span", { class: "home-sub", text: "None yet." })]),
    extra || null);
}

function addRow(label, listId, placeholder, onAdd) {
  const input = el("input", { type: "text", list: listId, placeholder, "aria-label": label });
  const note = el("span", { class: "home-sub" });
  const add = async () => {
    const value = input.value.trim();
    if (!value) return;
    const problem = await onAdd(value);
    note.textContent = problem || "";
    if (!problem) input.value = "";
  };
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") add(); });
  return el("div", { class: "add-row" }, input, el("button", { type: "button", class: "btn btn-quiet btn-small", onclick: add }, label), note);
}

async function catalogList() {
  if (!state.catalog.length) state.catalog = (await api("/api/catalog")).problems;
  return state.catalog;
}

async function findModule(value) {
  const v = value.toLowerCase();
  return (await catalogList()).find((p) => p.id === v || p.title.toLowerCase() === v);
}

async function fillOptions() {
  const problems = await catalogList();
  const modules = $("#module-options"), companies = $("#company-options");
  if (!modules.children.length) modules.replaceChildren(...problems.map((p) => el("option", { value: p.title })));
  if (!companies.children.length) {
    const names = [...new Set(problems.flatMap((p) => p.reports.map((r) => r.company)))].sort();
    companies.replaceChildren(...names.map((c) => el("option", { value: c })));
  }
}

async function saveInterests(updates) {
  try {
    state.profile = await api("/api/profile", { method: "PUT", body: updates });
    if (state.dash) state.dash.profile = state.profile;
    if (!$("#home").hidden) await loadHome();
    else if (!$("#catalog").hidden) renderCatalog();
    else if (!$("#paths").hidden) renderPaths();
  } catch (err) {
    showAppError(err);
  }
}

/* ---------- Progress: the numbers, kept off the Today page ---------- */
function progressSections(d) {
  const sections = [];
  if (d.profile.stack && d.profile.stack.length) sections.push(el("ul", { class: "stack", "aria-label": "Your stack" }, d.profile.stack.map((t) => el("li", { text: t }))));
  sections.push(el("a", { class: "btn btn-text btn-small back-link", href: "#/practice" }, "← Today"));
  sections.push(homeSection("Practice", el("div", { class: "week" }, el("p", { class: "home-sub", text: weekLine(d.week) }), calendar(d.active_days))));
  sections.push(homeSection("Your numbers", ledger(d.numbers)));
  if (gameOn()) sections.push(homeSection("Milestones", gameSection(d)));
  else sections.push(homeSection("Milestones", el("p", { class: "home-sub" }, "Grit and milestones are hidden. ",
    el("button", { type: "button", class: "btn btn-text btn-small", onclick: () => { setGame(true); renderHome(); } }, "Show them"))));
  if (!predictOn()) sections.push(el("p", { class: "home-sub" }, "Predict and explain is off. ",
    el("button", { type: "button", class: "btn btn-text btn-small", onclick: () => { setPredict(true); renderHome(); } }, "Turn it on")));
  if (d.recent.length) sections.push(homeSection("Recent", el("ol", { class: "log" }, d.recent.map(logLine))));
  return sections;
}

function weekLine(w) {
  return (w.this_week >= w.target ? `${plural(w.this_week, "practice day")} this week, target met. ` : `${w.this_week} of ${w.target} practice days this week. `)
    + (w.streak ? `Weekly streak: ${plural(w.streak, "week")}${w.repaired ? ", with one missed week forgiven" : ""}.`
      : w.sessions ? `${plural(w.sessions, "practice day")} so far.` : `A week counts toward your streak at ${w.target} practice days.`);
}

function daysAgo(iso) {
  const n = Math.round((new Date(isoDay(new Date())) - new Date(iso)) / 86400000);
  return n <= 0 ? "today" : n === 1 ? "yesterday" : `${n} days ago`;
}

/** The one bold element: a blade per skill. Its length is how sharp the skill is today. */
function edgeList(edges, game, d) {
  return el("ul", { class: "edges" }, edges.map((e) => {
    const bits = [];
    if (!e.built) bits.push("Not ready yet");
    else if (!e.state) bits.push("Not started");
    else bits.push(`${capital(e.label)}, practiced ${daysAgo(e.last_day)}`);
    const today = isoDay(new Date());
    const due = e.review_due ? el("span", { class: e.review_due <= today ? "due" : "", text: e.review_due <= today ? "Review due now" : `Review due ${shortDate(e.review_due)}` }) : null;
    const why = e.state ? `Best result: ${STATE_WORD[e.state]}. ${e.solved} of ${plural(e.questions, "question")} solved.` : "";
    const next = d.questions.find((r) => r.module === e.module && r.status !== "solved");
    const action = !e.built ? requestButton("build", e.module)
      : next ? el("a", { class: "btn btn-quiet btn-small", href: `#/${next.key}` }, next.status === "attempted" ? "Continue" : "Start")
        : requestButton("build", e.module, "Prepare next question");
    return el("li", { class: "edge", "data-label": e.label, title: why },
      el("span", { class: "edge-name" },
        el("span", { text: e.title }),
        e.ai_handled ? el("span", { class: "tag-ai", text: "your AI writes this at work" }) : null),
      el("span", { class: "blade", "aria-hidden": "true" }, el("span", { class: "blade-fill", style: `--s:${Math.round(e.sharpness * 100)}%` })),
      el("span", { class: "edge-state" }, el("span", { text: bits.join(". ") }), due,
        game && e.grit ? el("span", { class: "grit", title: GRIT_WORD[e.grit], text: `${e.grit} grit` }) : null),
      el("span", { class: "edge-actions" }, action,
        e.focus ? el("button", { type: "button", class: "btn btn-text btn-small", title: "Remove from your focus",
          onclick: () => saveInterests({ focus: d.profile.focus.filter((f) => f !== e.module) }) }, "Remove") : null));
  }));
}

const STATE_WORD = { mastered: "mastered", clean: "solved on your own", assisted: "solved with help", attempted: "attempted" };
const GRIT_WORD = { 220: "Started", 1000: "Solved", 3000: "Solved on your own", 6000: "Mastered: solved cleanly, and again after a gap", 8000: "Kept sharp through a long review" };

function edgeHelp(game) {
  return el("p", { class: "home-sub section-note", text: "A skill dulls with time since you last practiced it, and stays sharp longer once mastered."
    + (game ? " Grit is earned like a whetstone's: 220 started, 1000 solved, 3000 on your own, 6000 mastered, 8000 still sharp after a long review." : "") });
}

/** 26 weeks of practice days, one column per week, like a contribution graph. */
function calendar(activeDays) {
  const active = new Set(activeDays);
  const today = new Date();
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 7 * 25 - ((today.getDay() + 6) % 7));
  const cells = [];
  for (let d = new Date(start); d <= today; d.setDate(d.getDate() + 1)) {
    const iso = isoDay(d);
    cells.push(el("span", { class: `day${active.has(iso) ? " on" : ""}${iso === isoDay(today) ? " today" : ""}`, title: iso }));
  }
  return el("div", { class: "calendar", role: "img", "aria-label": `Practiced on ${activeDays.length} days in the last 26 weeks` }, cells);
}

function ledger(n) {
  if (!n.solved && !n.first_submits) return el("p", { class: "home-sub", text: "Your numbers appear after your first Submit." });
  const trend = n.hints_now !== null && n.hints_before !== null
    ? `, ${n.hints_now < n.hints_before ? "down" : n.hints_now > n.hints_before ? "up" : "level"} from ${n.hints_before} last month` : "";
  const rows = [
    ["Solved", n.solved, `${n.clean} on your own, ${n.assisted} with help`],
    ["Mastered", n.mastered, "solved cleanly, and again after a gap"],
    ["Runs to solve", n.median_runs, "median"],
    ["Hints per solve", n.hints_per_solve, `opened before solving${trend}`],
    ["First Submit", n.first_submit_rate === null ? null : `${n.first_submit_rate}%`, `passed every hidden test on the first try (${plural(n.first_submits, "question")})`],
    ["Predictions", n.predict_now === null ? null : `${n.predict_now}%`, `of test results you guessed right this month${n.predict_before !== null ? `, ${n.predict_now > n.predict_before ? "up" : n.predict_now < n.predict_before ? "down" : "level"} from ${n.predict_before}%` : ""}`],
  ].filter(([, v]) => v !== null && v !== undefined);
  return el("dl", { class: "ledger" }, rows.flatMap(([k, v, why]) => [
    el("dt", { text: k }), el("dd", {}, el("span", { class: "ledger-value", text: String(v) }), el("span", { class: "home-sub", text: why }))]));
}

function gameSection(d) {
  const r = d.records;
  const list = d.milestones.length
    ? el("ul", { class: "home-list" }, d.milestones.map((m) => homeRow(m.title, m.at ? `${m.detail}. ${shortDate(m.at)}.` : `${m.detail}.`, null)))
    : el("p", { class: "home-sub", text: "Milestones mark habits that make skills last: a clean solve, a passed review, a bug fixed from the report alone." });
  const recs = [
    r.clean_in_a_row ? `${plural(r.clean_in_a_row, "clean solve")} in a row` : null,
    r.fewest_runs ? `${plural(r.fewest_runs.runs, "run")} to solve ${r.fewest_runs.title}` : null,
    r.best_weekly_streak ? `best weekly streak: ${plural(r.best_weekly_streak, "week")}` : null,
  ].filter(Boolean);
  const off = el("button", { type: "button", class: "btn btn-text", onclick: () => { setGame(false); renderHome(); } }, "Hide grit and milestones");
  return el("div", {}, list, recs.length ? el("p", { class: "home-sub section-note", text: `Personal records: ${recs.join(", ")}.` }) : null, off);
}

function logLine(r) {
  const solved = r.mode === "submit" && r.status === "passed";
  return el("li", { "data-status": r.status },
    el("time", { datetime: r.created_at, text: `${shortDate(r.created_at)} ${r.created_at.slice(11, 16)}` }),
    el("span", { class: "log-mode", text: r.mode }),
    el("a", { href: `#/${r.challenge}`, text: r.title, title: r.challenge }),
    el("span", { class: "log-result", text: `${r.passed}/${r.total}${solved ? " passed" : ""}` }));
}

const SOLVED = new Set(["solved", "assisted", "mastered"]);
function setupSteps(d, paths) {
  const firstModule = (d.profile.focus || [])[0];
  return [
    { done: Boolean(d.profile.name || d.profile.role || d.profile.goal), title: "Set up your profile", short: "set up your profile", sub: "Your agent writes it from what it knows about you and your GitHub, plus a few questions.", action: requestButton("profile", "") },
    { done: (d.profile.focus || []).length > 0 || (d.profile.paths || []).length > 0 || paths.some((p) => p.mine), title: "Choose what to keep sharp", short: "choose what to keep sharp", sub: "Add skills to your focus below, or follow a path.", action: el("a", { class: "btn btn-secondary", href: "#/paths" }, "Browse paths") },
    { done: d.questions.length > 0, title: "Get your first question", short: "get your first question", sub: "Your agent writes it and Whetstone checks it.", action: firstModule ? requestButton("build", firstModule) : null },
    { done: d.questions.some((r) => SOLVED.has(r.status)), title: "Solve it", short: "solve your first question", sub: "Run the tests as you go, then Submit." },
  ];
}

const SETUP_KEY = "whetstone.setup";
function setupHidden() { try { return localStorage.getItem(SETUP_KEY) === "off"; } catch (_) { return false; } }
function hideSetup() { try { localStorage.setItem(SETUP_KEY, "off"); } catch (_) { /* per-viewer only */ } renderHome(); }

/** The checklist: one line once three steps are done, gone after the first solve or when hidden. */
function setupSection(steps, d) {
  const done = steps.filter((st) => st.done).length;
  if (done === steps.length || d.questions.some((r) => SOLVED.has(r.status)) || setupHidden()) return null;
  const hide = el("button", { type: "button", class: "btn btn-text btn-small", title: "Hide the checklist", onclick: hideSetup }, "Hide");
  if (done >= 3) {
    const next = steps.find((st) => !st.done);
    return el("p", { class: "setup-line home-sub" }, `${done} of ${steps.length} done: ${next.short}.`, next.action ? el("span", { class: "setup-action" }, next.action) : null, hide);
  }
  return homeSection("Get started", el("ol", { class: "setup" }, steps.map(setupItem)), null, hide);
}

function setupItem(st) {
  return el("li", { class: "setup-step", "data-done": st.done ? "true" : "false" },
    el("span", { class: "setup-title", text: st.title }),
    st.done ? null : el("span", { class: "home-sub", text: st.sub }),
    st.done || !st.action ? null : el("span", { class: "setup-action" }, st.action));
}

function homeSection(title, body, note, action) {
  return el("section", { class: "home-section" }, el("div", { class: "home-head" }, el("h2", { text: title }), action || null), note || null, body);
}

function homeRow(title, sub, action) {
  return el("li", { class: "home-row" },
    el("span", { class: "home-text" }, el("span", { class: "home-title", text: title }), el("span", { class: "home-sub", text: sub })),
    action);
}

/* ---------- Keyboard on list pages ---------- */
function listKeys(e) {
  if (e.metaKey || e.ctrlKey || e.altKey || document.querySelector("dialog[open]")) return;
  if (e.target.closest("input, textarea, select, [contenteditable='true'], .monaco-editor")) return;
  const view = !$("#catalog").hidden ? "catalog" : !$("#paths").hidden ? "paths" : !$("#design").hidden ? "design" : null;
  if (!view) return;
  if (e.key === "/") {
    e.preventDefault();
    $({ catalog: "#f-search", paths: "#p-search", design: "#d-search" }[view]).focus();
  } else if (view === "catalog" && (e.key === "j" || e.key === "k")) {
    const rows = $$("#catalog-grid .row");
    if (!rows.length) return;
    const i = rows.indexOf(document.activeElement);
    const next = rows[i < 0 ? 0 : Math.max(0, Math.min(rows.length - 1, i + (e.key === "j" ? 1 : -1)))];
    e.preventDefault();
    next.focus();
    next.scrollIntoView({ block: "nearest" });
  }
}

/* ---------- Routing ---------- */
function showView(view) {
  $("#home").hidden = view !== "home";
  $("#catalog").hidden = view !== "catalog";
  $("#paths").hidden = view !== "paths";
  $("#design").hidden = view !== "design";
  $("#workspace").hidden = view !== "practice";
  const nav = view === "home" ? "practice" : view;
  for (const v of ["catalog", "paths", "design", "practice"]) $(`#nav-${v}`).setAttribute("aria-current", nav === v ? "page" : "false");
}

/* ---------- Skeletons: a list page shows its shape until its data arrives ---------- */
const SKELETON = { home: ["#home-body", 4], paths: ["#paths-list", 6], design: ["#design-list", 5], catalog: ["#catalog-grid", 5] };
function skeletonRow(tag, cls) {
  return el(tag, { class: `skel ${cls}`, "aria-hidden": "true" }, el("span", { class: "skel-bar w-50" }), el("span", { class: "skel-bar w-80" }));
}
/** Fills an empty list with placeholder rows; a list that already has rows keeps them until the fresh ones land. */
function showSkeleton(view) {
  if (!SKELETON[view]) return;
  const [sel, n] = SKELETON[view];
  const box = $(sel);
  if (box.children.length) return;
  const rows = Array.from({ length: n }, () => skeletonRow(view === "home" ? "div" : "li", view === "paths" ? "skel-tile" : "skel-row"));
  box.replaceChildren(...(view === "home" ? [skeletonRow("div", "skel-card"), el("div", { class: "skel-list" }, rows)] : rows));
}
function viewFor(hash) {
  const parts = hash.replace(/^#\/?/, "").split("?")[0].split("/").filter(Boolean);
  return parts.length === 2 ? "practice" : ["paths", "design", "catalog"].includes(parts[0]) ? parts[0] : "home";
}

// A page that cannot load says why, instead of staying blank.
async function route() {
  $("#app-error").hidden = true;
  $("#app-error").classList.remove("info");
  try {
    await showRoute();
  } catch (err) {
    $$(".skel").forEach((s) => s.remove());
    showAppError(err);
  }
}

function showAppError(err) {
  const down = err instanceof TypeError; // fetch() itself failed: the server is not answering
  $("#app-error").replaceChildren(
    el("strong", { text: down ? "Whetstone is not answering. " : "This page could not load. " }),
    down ? "Start it with docker compose up -d (or bin/whetstone serve), then try again. " : `${err.message} `,
    el("button", { type: "button", class: "btn btn-quiet btn-small", onclick: () => location.reload() }, "Try again"));
  $("#app-error").hidden = false;
}

async function showRoute() {
  const parts = location.hash.replace(/^#\/?/, "").split("?")[0].split("/").filter(Boolean);
  const isChallenge = parts.length === 2
    && state.tracks.some((t) => t.id === parts[0] && t.challenges.some((c) => c.id === parts[1]));
  if (isChallenge) {
    showView("practice");
    await openChallenge(parts[0], parts[1]);
    return;
  }
  if (parts[0] === "paths") {
    showView("paths");
    showSkeleton("paths");
    document.title = "Paths · Whetstone";
    await loadPaths();
    return;
  }
  if (parts[0] === "design") {
    showView("design");
    showSkeleton("design");
    document.title = "Design · Whetstone";
    await loadDesign();
    return;
  }
  if (parts[0] === "catalog") {
    showView("catalog");
    showSkeleton("catalog");
    document.title = "Catalog · Whetstone";
    await loadCatalog();
    renderCatalog();
    return;
  }
  showView("home");
  showSkeleton("home");
  document.title = parts[0] === "progress" ? "Progress · Whetstone" : "Today · Whetstone";
  await loadHome();
}

/* ---------- Boot ---------- */
async function boot() {
  initTheme();
  $$(".tab").forEach((t) => t.addEventListener("click", () => selectTab(t.dataset.tab)));
  $("#next-hint").addEventListener("click", showNextHint);
  $("#reveal-solution").addEventListener("click", revealSolution);
  $("#run-btn").addEventListener("click", () => run("run"));
  $("#submit-btn").addEventListener("click", () => run("submit"));
  $("#reset-btn").addEventListener("click", resetCode);
  $("#results-toggle").addEventListener("click", toggleResults);
  $("#track-select").addEventListener("change", (e) => {
    const t = state.tracks.find((x) => x.id === e.target.value);
    const c = t && (t.challenges.find((x) => x.status !== "solved") || t.challenges[0]);
    if (c) location.hash = `#/${t.id}/${c.id}`;
  });
  document.addEventListener("keydown", (e) => {
    if (!state.useFallback) return;
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); run(e.shiftKey ? "submit" : "run"); }
  });
  window.addEventListener("beforeunload", () => { if (state.saveTimer) saveDraft(); });
  const mac = /Mac|iPhone|iPad/.test(navigator.platform);
  $$(".kbd").forEach((k) => { k.textContent = (mac ? "⌘" : "Ctrl ") + (k.dataset.keys === "submit" ? "⇧" : "") + "↵"; });
  initCatalog();
  initPeek();
  initStopTips();
  for (const [view, name] of [["practice", "target"], ["paths", "route"], ["design", "drafting-compass"], ["catalog", "library-big"]]) $(`#nav-${view}`).prepend(icon(name, "icon nav-icon"));
  PANE.addEventListener("change", onLayoutChange);
  PHONE.addEventListener("change", onLayoutChange);
  initPaths();
  initDesign();
  initPair();
  document.addEventListener("keydown", listKeys);

  // A list page shows its shape while the editor and the first fetches load; a question keeps the editor hidden until it mounts.
  const first = viewFor(location.hash);
  if (first !== "practice") { showView(first); showSkeleton(first); }
  const [config] = await Promise.all([api("/api/config"), initEditor(), loadTracks()]);
  state.config = config;
  window.addEventListener("hashchange", route);
  await route();
}

boot().catch(showAppError);
