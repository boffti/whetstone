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
  editor: null,
  models: {},
  useFallback: false,
  saveTimer: null,
  running: false,
  catalog: [],
  paths: [],
  pathFilter: { q: "", domain: "" },
  filters: { q: "", company: "", round: "", status: "" },
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
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (window.monaco) monaco.editor.setTheme(monacoTheme());
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
  // The editor follows the page: Claude's warm neutrals, clay for numbers and the cursor.
  monaco.editor.defineTheme("whetstone-light", {
    base: "vs", inherit: true,
    rules: [
      { token: "comment", foreground: "73726C", fontStyle: "italic" },
      { token: "keyword", foreground: "2F6497", fontStyle: "bold" },
      { token: "string", foreground: "2E7A4D" },
      { token: "number", foreground: "B8572F" },
    ],
    colors: {
      "editor.background": "#F5F4ED",
      "editor.lineHighlightBackground": "#EDEBE3",
      "editorLineNumber.foreground": "#A3A199",
      "editorLineNumber.activeForeground": "#3D3D3A",
      "editorCursor.foreground": "#B8572F",
      "editor.selectionBackground": "#DCE6F1",
    },
  });
  monaco.editor.defineTheme("whetstone-dark", {
    base: "vs-dark", inherit: true,
    rules: [
      { token: "comment", foreground: "9C9A92", fontStyle: "italic" },
      { token: "keyword", foreground: "8BB4DE", fontStyle: "bold" },
      { token: "string", foreground: "6CC08B" },
      { token: "number", foreground: "E8956F" },
    ],
    colors: {
      "editor.background": "#1F1E1D",
      "editor.lineHighlightBackground": "#2A2927",
      "editorLineNumber.foreground": "#5E5D58",
      "editorLineNumber.activeForeground": "#C2C0B6",
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
    ta.addEventListener("input", () => { if (state.activeFile === "solution.py") scheduleSave(); });
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
    return state.fallbackShowing === "solution.py" ? $("#fallback-editor").value : state.fallbackCode;
  }
  return state.models["solution.py"] ? state.models["solution.py"].getValue() : "";
}

function setFiles(code, files) {
  const all = [{ name: "solution.py", content: code, editable: true }, ...files.map((f) => ({ ...f, editable: false }))];
  if (state.useFallback) {
    state.fallbackFiles = all;
    state.fallbackCode = code;
    state.fallbackShowing = null;
  } else {
    Object.values(state.models).forEach((m) => m.dispose());
    state.models = {};
    for (const f of all) {
      const uri = monaco.Uri.parse(`file:///${state.challenge.track}/${state.challenge.id}/${f.name}`);
      const model = monaco.editor.createModel(f.content, "python", uri);
      if (f.editable) model.onDidChangeContent(() => scheduleSave());
      state.models[f.name] = model;
    }
  }
  renderFileTabs(all);
  showFile("solution.py");
}

function renderFileTabs(files) {
  const bar = $("#file-tabs");
  bar.replaceChildren(...files.map((f) => el("button", {
    class: "file-tab", role: "tab", type: "button", "data-file": f.name,
    "aria-selected": f.name === state.activeFile ? "true" : "false",
    onclick: () => showFile(f.name),
  }, f.name, f.editable ? null : el("span", { class: "ro", text: "read-only" }))));
}

function showFile(name) {
  if (state.useFallback) {
    const ta = $("#fallback-editor");
    if (state.fallbackShowing === "solution.py") state.fallbackCode = ta.value;
    const file = state.fallbackFiles.find((f) => f.name === name);
    ta.value = name === "solution.py" ? state.fallbackCode : file.content;
    ta.readOnly = name !== "solution.py";
    state.fallbackShowing = name;
  } else {
    state.editor.setModel(state.models[name]);
    state.editor.updateOptions({ readOnly: name !== "solution.py" });
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
  $("#track-options").replaceChildren(...state.tracks.map((t) => el("option", { value: t.id, label: t.title })));
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

async function loadStats() {
  const s = await api("/api/stats");
  const w = s.week;
  const streak = w.streak ? `Weekly streak: ${plural(w.streak, "week")}` : `${plural(w.sessions, "practice day")} so far`;
  $("#stats").replaceChildren(
    el("span", { title: `${streak}. A week counts at ${w.target} practice days.` }, el("strong", { text: w.this_week >= w.target ? plural(w.this_week, "day") : `${w.this_week} of ${w.target}` }), w.this_week >= w.target ? " this week" : " days this week"),
    el("span", {}, el("strong", { text: `${s.solved} of ${s.total}` }), " solved"),
  );
  fillDays($("#days"), s.active_days);
}

function isoDay(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function shortDate(iso) {
  return new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** The last 28 days, one square per day, lit when you practised. */
function fillDays(box, activeDays) {
  const active = new Set(activeDays);
  const today = new Date();
  const days = [];
  for (let i = 27; i >= 0; i--) {
    const iso = isoDay(new Date(today.getFullYear(), today.getMonth(), today.getDate() - i));
    days.push(el("span", { class: `day${active.has(iso) ? " on" : ""}${i === 0 ? " today" : ""}`, title: iso }));
  }
  box.replaceChildren(...days);
  box.setAttribute("aria-label", `Practised on ${active.size} of the last 28 days`);
}

/* ---------- Challenge ---------- */
async function openChallenge(trackId, cid) {
  if (state.challenge && !state.running) await saveDraft();
  const c = await api(`/api/challenges/${trackId}/${cid}`);
  state.challenge = c;
  state.trackId = trackId;
  state.hintsShown = c.hints.length;
  state.guessing = null;
  state.hintReady = c.hint_ready;
  // Problem first: some lessons open only after the first test run (docs/PEDAGOGY.md, rule 1).
  state.lessonLocked = c.lesson_mode === "after-run" && c.runs === 0 && !c.solved;
  state.activeFile = "solution.py";
  document.title = `${c.title} · Whetstone`;

  $("#challenge-title").textContent = c.title;
  const meta = [el("span", { class: "diff", "data-d": c.difficulty, text: capital(c.difficulty) }), el("span", { text: `About ${c.minutes} min` })];
  if (TYPE_LABEL[c.type]) meta.unshift(el("span", { class: "qtype", text: TYPE_LABEL[c.type] }));
  if (c.requires.includes("redis")) {
    const ok = state.config && state.config.redis_ok;
    meta.push(el("span", { class: `needs${ok ? " ok" : ""}`, text: ok ? "Redis connected" : "Needs Redis: not reachable" }));
  }
  meta.push(...c.tags.map((t) => el("span", { class: "tag", text: t })));
  $("#challenge-meta").replaceChildren(...meta);

  renderLesson();
  $("#panel-problem").innerHTML = c.problem_html;
  colorize($("#panel-problem"));
  $("#hint-list").replaceChildren(...c.hints.map((html) => { const li = el("li"); li.innerHTML = html; return li; }));
  colorize($("#hint-list"));
  updateHintButton();
  updateSolutionGate();
  $("#solution-code").hidden = true;
  selectTab(c.runs > 0 || state.lessonLocked ? "problem" : "lesson");

  setFiles(c.code, c.files);
  $("#save-state").textContent = c.code !== c.starter ? "Draft restored" : "";
  clearResults();
  $("#results").replaceChildren(el("p", { class: "results-empty", text: c.solved
    ? "You solved this one. Run it again any time, or try a cleaner solution."
    : "Run the tests to see results here. Visible tests check the basics. Submit also runs hidden tests for edge cases." }));
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
const REQUEST_LABEL = { build: "Build", variant: "Build review variant", "fill-path": "Build all missing modules", review: "Ask for a review", profile: "Set up my profile" };
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
  const r = state.requests[key];
  const button = (text, cls, onclick) => el("button", { type: "button", class: `btn ${cls}`, onclick }, text);
  let nodes;
  if (!r) {
    nodes = [button(wrap.dataset.label, "btn-secondary", () => sendRequest(kind, target))];
  } else if (r.status === "queued") {
    nodes = [el("span", { class: "req-state", text: state.agent.connected ? "Queued for your agent" : "Waiting for your agent" }),
      button("Cancel", "btn-text", () => cancelRequest(r.id))];
  } else if (r.status === "claimed") {
    nodes = [el("span", { class: "req-state working", text: "Your agent is building…" })];
  } else if (r.status === "done") {
    nodes = r.result && r.result.includes("/") ? [el("a", { class: "btn btn-primary", href: `#/${r.result}` }, "Start")] : [el("span", { class: "req-state done", text: "Done" })];
  } else {
    nodes = [el("span", { class: "req-state failed", text: `Not built: ${r.result || "your agent could not do it."}` }),
      button("Try again", "btn-text", () => sendRequest(kind, target))];
  }
  wrap.replaceChildren(...nodes);
}

async function sendRequest(kind, target) {
  try {
    const r = await api("/api/requests", { method: "POST", body: { kind, target } });
    state.requests[`${kind}:${r.target}`] = r;
    $$(".req").forEach(renderRequest);
    if (!state.agent.connected) showAgentHint();
  } catch (err) {
    showAppError(err);
  }
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
    if (!$("#home").hidden) loadHome();
    else if (!$("#paths").hidden) loadPaths();
  }
}

function renderAgentStatus() {
  const box = $("#agent-status");
  box.dataset.connected = String(Boolean(state.agent.connected));
  box.title = state.agent.connected
    ? "Your agent is watching Whetstone. Build buttons go straight to it."
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
  showFile("solution.py");
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
    panel.replaceChildren(el("p", { class: "panel-intro", text: "Try the problem first. The lesson opens after your first test run: attempting it before reading makes the idea stick." }));
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
    : `Hint ${state.hintsShown + 1} unlocks after your next test run`;
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
  $("#solution-intro").textContent = open
    ? "Compare the reference with your code. Name one difference, and why it matters."
    : "The reference opens after you solve it. If you are truly stuck, you can give up: that counts as solved with help, and a variant comes back in 2 days.";
  $("#reveal-solution").textContent = open ? "Show the reference solution" : "I give up: show the solution";
}

async function revealSolution() {
  const { track, id, solution_open: open } = state.challenge;
  if (!open && !confirm("Give up and see the reference solution? This question will count as solved with help.")) return;
  const s = await api(`/api/challenges/${track}/${id}/solution`, { method: "POST", body: { give_up: !open } });
  state.challenge.solution_open = true;
  $("#solution-gate").hidden = true;
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
    if (state.activeFile === "solution.py") $("#fallback-editor").value = r.code;
  } else {
    state.models["solution.py"].setValue(r.code);
  }
  showFile("solution.py");
  $("#save-state").textContent = "Reset to starter";
}

/* ---------- Running tests ---------- */
const STATUS_TEXT = { new: "not started", attempted: "in progress", assisted: "solved with help", solved: "solved", mastered: "mastered" };
const TYPE_LABEL = { predict: "Predict", fix: "Fix the bug", review: "Review", tests: "Write the tests", design: "Design" };
const VERDICT = { passed: "Passed", failed: "Not yet", error: "Could not run", timeout: "Timed out", blocked: "Blocked" };

/* ---------- Predict then explain (docs/PEDAGOGY.md, rule 8) ---------- */
const PREDICT_KEY = "whetstone.predict";
function predictOn() { try { return localStorage.getItem(PREDICT_KEY) !== "off"; } catch (_) { return true; } }
function setPredict(on) { try { localStorage.setItem(PREDICT_KEY, on ? "on" : "off"); } catch (_) { /* per-viewer only */ } }

// Ask on the first run of a question, and before each Submit until it is solved.
function wantsGuess(mode) {
  const c = state.challenge;
  if (!predictOn()) return false;
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
  if (guess === undefined && state.guessing && state.guessing.mode === mode) { state.guessing.send(); return; }
  if (guess === undefined && wantsGuess(mode)) { showGuess(mode); return; }
  state.guessing = null;
  state.running = true;
  clearTimeout(state.saveTimer);
  const runBtn = $("#run-btn"), subBtn = $("#submit-btn");
  runBtn.disabled = subBtn.disabled = true;
  // Set only the leading text node, so the shortcut hint inside the button survives.
  (mode === "run" ? runBtn : subBtn).firstChild.nodeValue = mode === "run" ? "Running… " : "Submitting… ";
  showResults("running", "Running…");
  $("#results").replaceChildren(el("p", { class: "results-empty", text: mode === "run" ? "Running the visible tests…" : "Running all tests, including hidden ones…" }));
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
    if (report.first_solve) { state.challenge.solution_open = true; updateSolutionGate(); }
    await Promise.all([loadTracks().then(renderRail), loadStats()]);
  } catch (err) {
    $("#results").replaceChildren(el("p", { class: "results-empty", text: `The run failed: ${err.message}` }));
    showResults("error", "Could not run");
  } finally {
    state.running = false;
    runBtn.disabled = subBtn.disabled = false;
    runBtn.firstChild.nodeValue = "Run tests ";
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
    el("span", { class: "verdict-sum", text: `${r.summary} (${r.duration.toFixed(1)} s)` })));

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
  const time = el("span", { class: "test-time", text: `${(t.duration * 1000).toFixed(0)} ms` });
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

/* ---------- Generate drawer ---------- */
function initGenerate() {
  const dialog = $("#generate-dialog");
  $("#open-generate").addEventListener("click", () => {
    const enabled = state.config && state.config.generator_enabled;
    $("#generate-disabled").hidden = enabled;
    $("#generate-fields").hidden = !enabled;
    const trackInput = dialog.querySelector("[name=track]");
    if (!trackInput.value) trackInput.value = state.trackId || "";
    dialog.showModal();
  });
  $("#generate-form").addEventListener("submit", async (e) => {
    if (e.submitter && e.submitter.value === "cancel") return;
    e.preventDefault();
    const form = new FormData(e.target);
    const btn = $("#generate-btn"), stateEl = $("#generate-state"), log = $("#generate-log");
    btn.disabled = true;
    stateEl.textContent = "Claude is writing and Whetstone is checking. This takes about a minute.";
    log.hidden = true;
    try {
      const res = await api("/api/generate", { method: "POST", body: {
        topic: form.get("topic"), track: form.get("track"), difficulty: form.get("difficulty"), notes: form.get("notes") || "",
      } });
      log.textContent = res.log.join("\n") + (res.ok ? "" : `\n\n${res.error}`);
      log.hidden = false;
      if (res.ok) {
        stateEl.textContent = "Added. Opening it now.";
        await loadTracks();
        location.hash = `#/${res.track}/${res.id}`;
        setTimeout(() => dialog.close(), 600);
      } else {
        stateEl.textContent = "The question did not pass the checks. Change the topic or notes and try again.";
      }
    } catch (err) {
      stateEl.textContent = err.message;
    } finally {
      btn.disabled = false;
    }
  });
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
    ? `${plural(reports, "interview report")} from ${counts.size} companies, grouped into ${plural(asked, "problem")}. Open one to see what was asked, then practise it with a lesson, an editor and tests.`
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
  if (p.format === "design") return { kind: "design", text: "Discussion only" };
  if (!p.links.length) return { kind: "none", text: "Not built yet" };
  const total = p.links.reduce((s, l) => s + l.total, 0);
  const solved = p.links.reduce((s, l) => s + l.solved, 0);
  return solved
    ? { kind: "progress", text: `${solved} of ${total} solved` }
    : { kind: "ready", text: `${plural(total, "question")} ready` };
}

/** One problem as a compact row: what it is, who asks it, how often, and two actions:
    add it to your focus, and practise it (or ask your agent to build it). */
function catalogRow(p, hits, max) {
  const companies = [...new Set(hits.map((r) => r.company))];
  const shown = companies.slice(0, 3).join(", ") + (companies.length > 3 ? ` and ${companies.length - 3} more` : "");
  const rounds = [...new Set(hits.map((r) => r.round))].map((r) => ROUNDS[r] || r).join(", ");
  const focus = (state.profile && state.profile.focus) || [];
  const inFocus = focus.includes(p.id);
  const link = p.links[0];
  const practise = p.format === "design" ? el("span", { class: "status", "data-s": "design", text: "Discussion only" })
    : link ? el("a", { class: "btn btn-quiet btn-small", href: `#/${link.track}/${link.challenge}` }, link.solved ? "Continue" : "Start")
      : requestButton("build", p.id);
  return el("div", { class: "row-item" },
    el("button", { type: "button", class: "row", title: rounds, onclick: () => openProblem(p.id) },
      el("span", { class: "row-main" },
        el("span", { class: "row-head" }, el("span", { class: "row-title", text: p.title }), el("span", { class: "row-cos", text: shown })),
        el("span", { class: "row-sub", text: p.summary })),
      el("span", { class: "row-asked" },
        el("span", { class: "freq", style: `--w:${Math.round((hits.length / max) * 100)}%`, "aria-hidden": "true" }),
        el("span", {}, el("strong", { text: hits.length }), hits.length === 1 ? " report" : " reports"))),
    el("span", { class: "row-actions" },
      el("button", { type: "button", class: `btn btn-text btn-small focus-toggle`, "aria-pressed": String(inFocus),
        title: inFocus ? "Remove from your focus" : "Add to your focus",
        onclick: () => saveInterests({ focus: inFocus ? focus.filter((x) => x !== p.id) : [...focus, p.id] }) }, inFocus ? "✓ In focus" : "+ Focus"),
      practise));
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
      el("strong", { text: r.company }),
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
    nodes.push(el("p", { class: "note", text: "This is a discussion round, so there are no tests to run. Read what people were asked and sketch your answer." }));
  } else if (state.config && state.config.generator_enabled) {
    nodes.push(el("button", {
      type: "button", class: `btn ${p.links.length ? "btn-quiet" : "btn-primary"}`, id: "build-btn", onclick: () => buildProblem(p),
    }, `Build ${own ? "the next" : "a"} question`));
  } else {
    nodes.push(el("div", { class: "agent-ask" },
      el("p", { class: "note", text: `Your agent builds ${own ? "the next" : "a"} question for you on your own AI subscription, and Whetstone checks it before it appears here.` }),
      requestButton("build", p.id, own ? "Build the next question" : "Build a question")));
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
    await Promise.all([loadTracks(), loadStats()]);
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
function initPaths() {
  $("#p-search").addEventListener("input", (e) => { state.pathFilter.q = e.target.value.trim().toLowerCase(); renderPaths(); });
  const dialog = $("#path-dialog");
  $("#path-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
}

async function loadPaths() {
  // Reload modules too, so a module the agent just built links straight into Practice.
  const [paths, profile] = await Promise.all([api("/api/paths"), api("/api/profile"), loadTracks()]);
  state.profile = profile;
  state.paths = paths;
  const counts = new Map();
  for (const p of paths) counts.set(p.domain || "Other", (counts.get(p.domain || "Other") || 0) + 1);
  const chip = (value, label) => el("button", {
    type: "button", class: "chip", "data-domain": value, "aria-pressed": state.pathFilter.domain === value ? "true" : "false",
    onclick: () => {
      state.pathFilter.domain = value;
      $$("#p-domains .chip").forEach((c) => c.setAttribute("aria-pressed", c.dataset.domain === value ? "true" : "false"));
      renderPaths();
    },
  }, label);
  $("#p-domains").replaceChildren(chip("", "All domains"),
    ...[...counts].sort((x, y) => x[0].localeCompare(y[0])).map(([d, n]) => chip(d, `${d} (${n})`)));
  const companies = new Set(paths.flatMap((p) => p.companies));
  $("#paths-lede").textContent = paths.length
    ? `${plural(paths.length, "system")} to build${companies.size ? `, modelled on ${plural(companies.size, "company", "companies")}` : ""}. Pick one you want to understand. Modules marked "not built" are placeholders: your AI agent builds each one when you get there.`
    : "No learning paths yet.";
  renderPaths();
}

function pathStats(p) {
  const built = p.modules.filter((m) => m.built);
  return {
    built: built.length,
    total: built.reduce((s, m) => s + m.questions, 0),
    solved: built.reduce((s, m) => s + m.solved, 0),
  };
}

function pathText(p) {
  p._text ??= [p.title, p.goal, p.domain, ...p.companies, ...p.modules.map((m) => `${m.title} ${m.summary || ""}`)].join(" ").toLowerCase();
  return p._text;
}

function renderPaths() {
  const f = state.pathFilter;
  const filtering = Boolean(f.q || f.domain);
  const followed = new Set((state.profile && state.profile.paths) || []);
  const started = (p) => p.mine || followed.has(p.id) || pathStats(p).solved > 0;
  // Your paths sit in their own list above the grid, unless you are searching.
  const yours = filtering ? [] : state.paths.filter(started);
  const rows = state.paths
    .filter((p) => (filtering || !started(p)) && (!f.domain || (p.domain || "Other") === f.domain) && (!f.q || pathText(p).includes(f.q)))
    .map((p) => ({ p, st: pathStats(p) }))
    // The ones with the most built come first, then A to Z.
    .sort((x, y) => y.st.built - x.st.built || x.p.title.localeCompare(y.p.title));
  $("#paths-yours").replaceChildren(...(yours.length ? [el("h2", { text: "Your paths" }), el("ul", { class: "home-list" }, yours.map(yourPathRow))] : []));
  $("#paths-count").textContent = rows.length ? `${yours.length ? "More paths: " : "Showing "}${plural(rows.length, "path")}.` : "";
  $("#paths-list").replaceChildren(...(rows.length ? rows.map(({ p, st }) => el("li", {}, pathTile(p, st))) : [el("li", { class: "agent-ask" },
    el("p", { class: "note", text: state.paths.length ? "Nothing matches. Clear a filter, or ask your agent for a new path:" : "No learning paths yet. Open this folder in Claude Code, Codex, Cursor or another coding agent and ask:" }),
    el("p", { class: "ask-line" }, el("code", { text: "Make me a Whetstone learning path to build …" })))]));
}

/** A path as a strip of modules: solved, built, or not built yet. */
function routeStrip(p) {
  return el("span", { class: "route", "aria-hidden": "true" }, p.modules.map((m) =>
    el("span", { class: "route-seg", title: m.title, "data-s": m.built && m.questions && m.solved === m.questions ? "done" : m.built ? "built" : "none" })));
}

function pathSummary(p, st) {
  return `${st.built} of ${plural(p.modules.length, "module")} built` + (st.total ? `, ${st.solved} of ${plural(st.total, "question")} solved` : "");
}

function yourPathRow(p) {
  const st = pathStats(p);
  const m = p.modules.find((x) => !x.built || x.solved < x.questions);
  const action = !m ? el("button", { type: "button", class: "btn btn-quiet", onclick: () => openPath(p.id) }, "Review")
    : m.built ? el("a", { class: "btn btn-primary", href: `#/${m.module}/${m.next}` }, m.solved ? `Continue: ${m.title}` : `Start: ${m.title}`)
      : requestButton("build", m.module, `Build: ${m.title}`);
  return el("li", { class: "home-row" },
    el("button", { type: "button", class: "home-text link-like", onclick: () => openPath(p.id) },
      el("span", { class: "home-title", text: p.title }),
      routeStrip(p),
      el("span", { class: "home-sub", text: pathSummary(p, st) })),
    action);
}

function pathTile(p, st) {
  return el("button", { type: "button", class: "card path-tile", onclick: () => openPath(p.id) },
    el("span", { class: "path-domain" }, p.domain || "Other", p.mine ? el("span", { class: "tag-mine", text: "Yours" }) : null),
    el("span", { class: "card-title", text: p.title }),
    p.goal ? el("span", { class: "card-summary", text: p.goal }) : null,
    p.companies.length ? el("span", { class: "card-companies", text: p.companies.slice(0, 4).join(", ") + (p.companies.length > 4 ? ` and ${p.companies.length - 4} more` : "") }) : null,
    el("span", { class: "card-foot path-foot" }, routeStrip(p), el("span", { class: "card-rounds", text: pathSummary(p, st) })));
}

function openPath(id) {
  const p = state.paths.find((x) => x.id === id);
  if (!p) return;
  $("#path-detail").replaceChildren(pathCard(p));
  $("#path-dialog").showModal();
  $("#path-dialog .drawer-inner").scrollTop = 0;
}

function pathCard(p) {
  const st = pathStats(p);
  const current = p.modules.findIndex((m) => m.built && m.solved < m.questions);
  return el("section", { class: "path", "aria-labelledby": `path-${p.id}` },
    el("span", { class: "wear", style: `--w:${st.total ? Math.round((st.solved / st.total) * 100) : 0}%`, "aria-hidden": "true" }),
    p.domain ? el("p", { class: "path-domain", text: p.domain }) : null,
    p.companies.length ? el("p", { class: "path-companies", text: p.companies.join(", ") }) : null,
    el("h2", { id: `path-${p.id}`, text: p.title }),
    followButton(p),
    p.goal ? el("p", { class: "path-goal", text: p.goal }) : null,
    el("p", { class: "path-sum", text: `${pathSummary(p, st)}.` }),
    p.modules.some((m) => !m.built) ? el("div", { class: "agent-ask fill-ask" },
      el("p", { class: "note", text: `${plural(p.modules.filter((m) => !m.built).length, "module")} not built yet. Ask your agent to build the first question of each:` }),
      requestButton("fill-path", p.id)) : null,
    p.modules.length
      ? el("ol", { class: "path-line" }, p.modules.map((m, i) => moduleStep(m, i, i === current)))
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

function moduleStep(m, i, isCurrent) {
  const kind = !m.built ? "none" : m.solved === m.questions ? "done" : m.solved ? "progress" : "ready";
  let action;
  if (m.built) {
    action = el("a", { class: `btn ${isCurrent ? "btn-primary" : "btn-secondary"}`, href: `#/${m.module}/${m.next}`, onclick: () => $("#path-dialog").close() },
      { ready: "Start", progress: "Continue", done: "Review" }[kind]);
  } else {
    action = requestButton("build", m.module);
  }
  const sub = m.built
    ? `${m.solved} of ${plural(m.questions, "question")} solved`
    : `Not built yet${m.reports ? `, seen in ${plural(m.reports, "interview report")}` : ""}.`;
  return el("li", { class: "path-step", "data-s": kind, "aria-current": isCurrent ? "step" : null },
    el("span", { class: "notch", "aria-hidden": "true" }, kind === "done" ? "✓" : String(i + 1)),
    el("div", { class: "path-step-body" },
      el("div", { class: "path-step-text" },
        el("span", { class: "path-step-title", text: m.title }),
        m.summary ? el("span", { class: "path-step-what", text: m.summary }) : null,
        el("span", { class: "path-step-sub", text: sub })),
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
  $("#home-title").textContent = progress ? "Your progress" : d.profile.name || "Today";
  const lede = [d.profile.role, d.profile.goal ? `Goal: ${d.profile.goal}` : ""].filter(Boolean).map((t) => t.replace(/\.$/, "")).join(". ");
  $("#home-lede").textContent = progress ? weekLine(d.week) : lede ? `${lede}.` : weekLine(d.week);
  $("#home-body").replaceChildren(...(progress ? progressSections(d) : todaySections(d, state.paths)));
}

/* ---------- Today: one next step, then your focus ---------- */
function todaySections(d, paths) {
  const sections = [];
  if (d.profile.stack && d.profile.stack.length) sections.push(el("ul", { class: "stack", "aria-label": "Your stack" }, d.profile.stack.map((t) => el("li", { text: t }))));
  const setup = setupSteps(d, paths);
  if (setup.some((st) => !st.done)) sections.push(homeSection("Get started", el("ol", { class: "setup" }, setup.map(setupItem))));

  const picks = todayPicks(d, paths);
  if (picks.length) {
    sections.push(homeSection("Today", el("ul", { class: "today" },
      picks.map((pk, i) => el("li", { class: `today-item${i ? "" : " main"}` },
        el("span", { class: "home-text" },
          el("span", { class: "today-kind", text: i ? `Or: ${pk.kind}` : pk.kind }),
          el("span", { class: "home-title", text: pk.title }),
          el("span", { class: "home-sub", text: pk.why })),
        pk.action)))));
  }
  sections.push(homeSection("Your focus", focusSection(d), el("p", { class: "home-sub section-note", text: "The skills, companies and paths you want to keep sharp. Your agent reads this list too." })));
  const w = d.week;
  sections.push(el("a", { class: "progress-link", href: "#/progress" },
    el("span", { class: "home-title", text: "Your progress" }),
    el("span", { class: "home-sub", text: `${w.this_week} of ${w.target} practice days this week. ${w.streak ? `${plural(w.streak, "week")} streak. ` : ""}${plural(d.numbers.solved, "question")} solved. Calendar, numbers and milestones →` })));
  return sections;
}

/** Up to two next steps, most useful first: a due review, the question in progress,
    the next step in a path you follow, then something new in your focus. */
function todayPicks(d, paths) {
  const q = d.questions;
  const today = isoDay(new Date());
  const start = (r, verb) => el("a", { class: "btn btn-primary", href: `#/${r.key}` }, verb);
  const picks = [];
  for (const r of q.filter((x) => x.review_due && x.review_due <= today)) {
    const variant = q.find((x) => x.variant_of === r.key && x.status !== "solved");
    picks.push({ kind: "Review", title: variant ? variant.title : r.title, target: r.key,
      why: `Solved on ${shortDate(r.solved_at)}. A fresh variant checks that it stuck.`,
      action: variant ? start(variant, "Start review") : requestButton("variant", r.key, "Build review variant") });
  }
  const open = q.filter((r) => r.status === "attempted").sort((a, b) => b.last_run.created_at.localeCompare(a.last_run.created_at));
  for (const r of open.slice(0, 2)) {
    picks.push({ kind: "Continue", title: r.title, target: r.key,
      why: `Last run ${shortDate(r.last_run.created_at)}: ${r.last_run.passed} of ${r.last_run.total} tests passed.`, action: start(r, "Continue") });
  }
  const followed = new Set(d.profile.paths || []);
  for (const p of paths.filter((x) => followed.has(x.id) || x.mine || pathStats(x).solved)) {
    const m = p.modules.find((x) => !x.built || x.solved < x.questions);
    if (!m) continue;
    picks.push({ kind: "Next in your path", title: m.title, target: m.module, why: p.title,
      action: m.built ? el("a", { class: "btn btn-primary", href: `#/${m.module}/${m.next}` }, "Start") : requestButton("build", m.module) });
  }
  for (const e of d.edges.filter((x) => x.focus && !x.built)) {
    picks.push({ kind: "From your focus", title: e.title, target: e.module, why: "Not built yet. Your agent builds the first question.", action: requestButton("build", e.module) });
  }
  const fresh = q.find((r) => r.status === "new");
  if (fresh) picks.push({ kind: "Start something new", title: fresh.title, target: fresh.key, why: moduleName(fresh.module), action: start(fresh, "Start") });
  const seen = new Set();
  return picks.filter((pk) => !seen.has(pk.target) && seen.add(pk.target)).slice(0, 2);
}

function moduleName(id) { return (state.tracks.find((t) => t.id === id) || { title: id }).title; }

/** Your focus: each skill's edge, plus the companies and paths you follow. All editable. */
function focusSection(d) {
  const profile = d.profile;
  const box = el("div", { class: "focus" });
  box.append(d.edges.length ? edgeList(d.edges, gameOn(), d) : el("p", { class: "home-sub", text: "Nothing in your focus yet. Add a skill below, or from the Catalog." }));
  box.append(addRow("Add a skill", "module-options", "Rate limiter, Job scheduler…", async (value) => {
    const p = await findModule(value);
    if (!p) return "Pick a skill from the list.";
    await saveInterests({ focus: [...(profile.focus || []), p.id] });
  }));
  box.append(chipList("Companies", profile.targets || [], (c) => saveInterests({ targets: profile.targets.filter((x) => x !== c) })));
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

function chipList(label, items, onRemove, extra) {
  return el("div", { class: "chip-row" }, el("span", { class: "chip-row-label", text: label }),
    ...(items.length ? items.map((item) => el("span", { class: "chip-tag" }, item,
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
  const sections = [el("a", { class: "btn btn-text btn-small back-link", href: "#/practice" }, "← Today")];
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
    if (!e.built) bits.push("Not built yet");
    else if (!e.state) bits.push("Not started");
    else bits.push(`${capital(e.label)}, practised ${daysAgo(e.last_day)}`);
    const today = isoDay(new Date());
    const due = e.review_due ? el("span", { class: e.review_due <= today ? "due" : "", text: e.review_due <= today ? "Review due now" : `Review due ${shortDate(e.review_due)}` }) : null;
    const why = e.state ? `Best result: ${STATE_WORD[e.state]}. ${e.solved} of ${plural(e.questions, "question")} solved.` : "";
    const next = d.questions.find((r) => r.module === e.module && r.status !== "solved");
    const action = !e.built ? requestButton("build", e.module)
      : next ? el("a", { class: "btn btn-quiet btn-small", href: `#/${next.key}` }, next.status === "attempted" ? "Continue" : "Start")
        : requestButton("build", e.module, "Build next question");
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
  return el("p", { class: "home-sub section-note", text: "A skill dulls with time since you last practised it, and stays sharp longer once mastered."
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
  return el("div", { class: "calendar", role: "img", "aria-label": `Practised on ${activeDays.length} days in the last 26 weeks` }, cells);
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

function setupSteps(d, paths) {
  const firstModule = (d.profile.focus || [])[0];
  return [
    { done: Boolean(d.profile.name || d.profile.role || d.profile.goal), title: "Set up your profile", sub: "Your agent writes it from what it knows about you and your GitHub, plus a few questions.", action: requestButton("profile", "") },
    { done: (d.profile.focus || []).length > 0 || (d.profile.paths || []).length > 0 || paths.some((p) => p.mine), title: "Choose what to keep sharp", sub: "Add skills to your focus below, or follow a path.", action: el("a", { class: "btn btn-secondary", href: "#/paths" }, "Browse paths") },
    { done: d.questions.length > 0, title: "Build your first question", sub: "Your agent writes it and Whetstone checks it.", action: firstModule ? requestButton("build", firstModule) : null },
    { done: d.questions.some((r) => r.status === "solved"), title: "Solve it", sub: "Run the tests as you go, then Submit." },
  ];
}

function setupItem(st) {
  return el("li", { class: "setup-step", "data-done": st.done ? "true" : "false" },
    el("span", { class: "setup-title", text: st.title }),
    st.done ? null : el("span", { class: "home-sub", text: st.sub }),
    st.done || !st.action ? null : el("span", { class: "setup-action" }, st.action));
}

function homeSection(title, body, note) {
  return el("section", { class: "home-section" }, el("h2", { text: title }), note || null, body);
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
  const view = !$("#catalog").hidden ? "catalog" : !$("#paths").hidden ? "paths" : null;
  if (!view) return;
  if (e.key === "/") {
    e.preventDefault();
    $(view === "catalog" ? "#f-search" : "#p-search").focus();
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
  $("#workspace").hidden = view !== "practice";
  const nav = view === "home" ? "practice" : view;
  for (const v of ["catalog", "paths", "practice"]) $(`#nav-${v}`).setAttribute("aria-current", nav === v ? "page" : "false");
}

// A page that cannot load says why, instead of staying blank.
async function route() {
  $("#app-error").hidden = true;
  $("#app-error").classList.remove("info");
  try {
    await showRoute();
  } catch (err) {
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
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  const isChallenge = parts.length === 2
    && state.tracks.some((t) => t.id === parts[0] && t.challenges.some((c) => c.id === parts[1]));
  if (isChallenge) {
    showView("practice");
    await openChallenge(parts[0], parts[1]);
    return;
  }
  if (parts[0] === "paths") {
    showView("paths");
    document.title = "Paths · Whetstone";
    await loadPaths();
    return;
  }
  if (parts[0] === "catalog") {
    showView("catalog");
    document.title = "Catalog · Whetstone";
    await loadCatalog();
    renderCatalog();
    return;
  }
  showView("home");
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
  initGenerate();
  initCatalog();
  PANE.addEventListener("change", onLayoutChange);
  PHONE.addEventListener("change", onLayoutChange);
  initPaths();
  initPair();
  document.addEventListener("keydown", listKeys);

  const [config] = await Promise.all([api("/api/config"), initEditor(), loadTracks()]);
  state.config = config;
  await loadStats();
  window.addEventListener("hashchange", route);
  await route();
}

boot().catch(showAppError);
