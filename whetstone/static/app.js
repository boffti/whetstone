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
  filters: { q: "", company: "", round: "", tracked: false },
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
  monaco.editor.defineTheme("whetstone-light", {
    base: "vs", inherit: true,
    rules: [
      { token: "comment", foreground: "6B7781", fontStyle: "italic" },
      { token: "keyword", foreground: "1D6C96", fontStyle: "bold" },
      { token: "string", foreground: "1C8550" },
      { token: "number", foreground: "C65F1A" },
    ],
    colors: {
      "editor.background": "#F4F6F7",
      "editor.lineHighlightBackground": "#EAEDF0",
      "editorLineNumber.foreground": "#9AA5AE",
      "editorLineNumber.activeForeground": "#4A5661",
      "editorCursor.foreground": "#C65F1A",
      "editor.selectionBackground": "#CFE2EE",
    },
  });
  monaco.editor.defineTheme("whetstone-dark", {
    base: "vs-dark", inherit: true,
    rules: [
      { token: "comment", foreground: "808C96", fontStyle: "italic" },
      { token: "keyword", foreground: "86BEDC", fontStyle: "bold" },
      { token: "string", foreground: "5DC88F" },
      { token: "number", foreground: "F0A060" },
    ],
    colors: {
      "editor.background": "#191E23",
      "editor.lineHighlightBackground": "#20262C",
      "editorLineNumber.foreground": "#56616B",
      "editorLineNumber.activeForeground": "#A7B1B9",
      "editorCursor.foreground": "#E8863A",
      "editor.selectionBackground": "#2B4556",
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
    el("span", { title: `${streak}. A week counts at ${w.target} practice days.` }, el("strong", { text: `${w.this_week} of ${w.target}` }), " days this week"),
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
  $("#hint-list").replaceChildren(...c.hints.map((html) => { const li = el("li"); li.innerHTML = html; return li; }));
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

function renderLesson() {
  const panel = $("#panel-lesson");
  if (state.lessonLocked) {
    panel.replaceChildren(el("p", { class: "panel-intro", text: "Try the problem first. The lesson opens after your first test run: attempting it before reading makes the idea stick." }));
  } else {
    panel.innerHTML = state.challenge.lesson_html;
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
  pre.querySelector("code").textContent = s.code;
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
const TYPE_LABEL = { predict: "Predict", fix: "Fix the bug", review: "Review" };
const VERDICT = { passed: "Passed", failed: "Not yet", error: "Could not run", timeout: "Timed out", blocked: "Blocked" };

async function run(mode) {
  if (!state.challenge || state.running) return;
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
    const report = await api(`/api/challenges/${track}/${id}/run`, { method: "POST", body: { code: getCode(), mode } });
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
  chip.replaceChildren(el("span", { class: "chip-word", text: count ? `${word} ` : word }), count ? el("span", { text: count }) : null);
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
  const nodes = [];
  if (r.first_solve) nodes.push(el("p", { class: "solved-note", text: r.solve === "assisted"
    ? "Solved with help. A variant of this question comes back for review in 2 days."
    : "Solved on your own. A variant comes back for review in 3 days, to make it stick." }));
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
  $("#f-tracked").addEventListener("change", (e) => { state.filters.tracked = e.target.checked; renderCatalog(); });
  const dialog = $("#problem-dialog");
  $("#problem-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
}

async function loadCatalog() {
  state.catalog = (await api("/api/catalog")).problems;
  const counts = new Map();
  for (const p of state.catalog) for (const r of p.reports) counts.set(r.company, (counts.get(r.company) || 0) + 1);
  const select = $("#f-company");
  const keep = select.value;
  select.replaceChildren(el("option", { value: "", text: "All companies" }),
    ...[...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([c, n]) => el("option", { value: c, text: `${c} (${n})` })));
  select.value = keep;
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
    .filter(({ p, hits }) => hits.length && (!f.tracked || p.links.length) && (!f.q || searchText(p).includes(f.q)))
    .sort((a, b) => b.hits.length - a.hits.length || a.p.title.localeCompare(b.p.title));
  const max = Math.max(1, ...rows.map((r) => r.hits.length));
  const n = rows.reduce((s, r) => s + r.hits.length, 0);
  $("#catalog-count").textContent = rows.length
    ? `Showing ${plural(rows.length, "problem")} and ${plural(n, "report")}, most asked first.`
    : "Nothing matches. Clear a filter or try another word.";
  $("#catalog-grid").replaceChildren(...rows.map(({ p, hits }) => el("li", {}, card(p, hits, max))));
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

function card(p, hits, max) {
  const companies = [...new Set(hits.map((r) => r.company))];
  const shown = companies.slice(0, 4).join(", ") + (companies.length > 4 ? ` and ${companies.length - 4} more` : "");
  const rounds = [...new Set(hits.map((r) => r.round))].map((r) => ROUNDS[r] || r).join(", ");
  const st = problemStatus(p);
  return el("button", { type: "button", class: "card", onclick: () => openProblem(p.id) },
    el("span", { class: "wear", style: `--w:${Math.round((hits.length / max) * 100)}%`, "aria-hidden": "true" }),
    el("span", { class: "card-top" },
      el("span", { class: "card-title", text: p.title }),
      el("span", { class: "card-count" }, el("strong", { text: hits.length }), hits.length === 1 ? " report" : " reports")),
    el("span", { class: "card-summary", text: p.summary }),
    el("span", { class: "card-companies", text: shown }),
    el("span", { class: "card-foot" },
      el("span", { class: "card-rounds", text: rounds }),
      el("span", { class: "status", "data-s": st.kind, text: st.text })));
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
    links.length ? el("p", { class: "report-src" }, "Sources: ",
      ...links.flatMap((u, i) => [i ? ", " : null,
        el("a", { href: u.href, target: "_blank", rel: "noopener noreferrer", text: u.hostname.replace(/^www\./, "") })])) : null);
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
    const ask = `Build the ${own ? "next " : "first "}Whetstone question for the ${p.id} module.`;
    const copy = el("button", { type: "button", class: "btn btn-quiet", onclick: () => copyText(ask, copy) }, "Copy request");
    nodes.push(el("div", { class: "agent-ask" },
      el("p", { class: "note", text: "Build it with your own AI subscription. Open this folder in Claude Code, Codex, Cursor or another coding agent and ask:" }),
      el("p", { class: "ask-line" }, el("code", { text: ask }), copy),
      el("p", { class: "note" }, "The agent follows ", el("code", { text: "AGENTS.md" }), " and the ", el("code", { text: "bin/whetstone" }), " CLI. Whetstone checks the question before adding it here.")));
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
  const [paths] = await Promise.all([api("/api/paths"), loadTracks()]);
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
  const rows = state.paths
    .filter((p) => (!f.domain || (p.domain || "Other") === f.domain) && (!f.q || pathText(p).includes(f.q)))
    .map((p) => ({ p, st: pathStats(p) }))
    // Paths you have started come first, then the ones with the most built, then A to Z.
    .sort((x, y) => y.p.mine - x.p.mine || (y.st.solved > 0) - (x.st.solved > 0) || y.st.built - x.st.built || x.p.title.localeCompare(y.p.title));
  $("#paths-count").textContent = rows.length ? `Showing ${plural(rows.length, "path")}.` : "";
  $("#paths-list").replaceChildren(...(rows.length ? rows.map(({ p, st }) => el("li", {}, pathTile(p, st))) : [el("li", { class: "agent-ask" },
    el("p", { class: "note", text: state.paths.length ? "Nothing matches. Clear a filter, or ask your agent for a new path:" : "No learning paths yet. Open this folder in Claude Code, Codex, Cursor or another coding agent and ask:" }),
    el("p", { class: "ask-line" }, el("code", { text: "Make me a Whetstone learning path to build …" })))]));
}

function pathTile(p, st) {
  const pct = st.total ? Math.round((st.solved / st.total) * 100) : 0;
  const status = st.solved ? `${st.solved} of ${plural(st.total, "question")} solved` : `${st.built} of ${plural(p.modules.length, "module")} built`;
  return el("button", { type: "button", class: "card path-tile", onclick: () => openPath(p.id) },
    el("span", { class: "wear", style: `--w:${pct}%`, "aria-hidden": "true" }),
    el("span", { class: "path-domain" }, p.domain || "Other", p.mine ? el("span", { class: "tag-mine", text: "Yours" }) : null),
    el("span", { class: "card-title", text: p.title }),
    p.goal ? el("span", { class: "card-summary", text: p.goal }) : null,
    p.companies.length ? el("span", { class: "card-companies", text: p.companies.slice(0, 4).join(", ") + (p.companies.length > 4 ? ` and ${p.companies.length - 4} more` : "") }) : null,
    el("span", { class: "card-foot" },
      el("span", { class: "card-rounds", text: p.modules.map((m) => m.title).slice(0, 3).join(" → ") + (p.modules.length > 3 ? " → …" : "") }),
      el("span", { class: "status", "data-s": st.solved ? "progress" : st.built ? "ready" : "none", text: status })));
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
    p.goal ? el("p", { class: "path-goal", text: p.goal }) : null,
    el("p", { class: "path-sum", text: `${st.solved} of ${plural(st.total, "question")} solved. ${st.built} of ${plural(p.modules.length, "module")} built.` }),
    p.modules.length
      ? el("ol", { class: "path-line" }, p.modules.map((m, i) => moduleStep(m, i, i === current)))
      : el("p", { class: "path-sum" }, "No modules yet. Ask your agent to add some, or run ", el("code", { text: `bin/whetstone path add ${p.id} <module>` })));
}

function moduleStep(m, i, isCurrent) {
  const kind = !m.built ? "none" : m.solved === m.questions ? "done" : m.solved ? "progress" : "ready";
  let action;
  if (m.built) {
    action = el("a", { class: `btn ${isCurrent ? "btn-primary" : "btn-secondary"}`, href: `#/${m.module}/${m.next}`, onclick: () => $("#path-dialog").close() },
      { ready: "Start", progress: "Continue", done: "Review" }[kind]);
  } else {
    const ask = `Build the first Whetstone question for the ${m.module} module.`;
    const copy = el("button", { type: "button", class: "btn btn-quiet", onclick: () => copyText(ask, copy) }, "Copy request");
    action = el("p", { class: "ask-line" }, el("code", { text: ask }), copy);
  }
  const sub = m.built
    ? `${m.solved} of ${plural(m.questions, "question")} solved`
    : `Not built yet${m.reports ? `, seen in ${plural(m.reports, "interview report")}` : ""}. Ask your agent:`;
  return el("li", { class: "path-step", "data-s": kind, "aria-current": isCurrent ? "step" : null },
    el("span", { class: "notch", "aria-hidden": "true" }, kind === "done" ? "✓" : String(i + 1)),
    el("div", { class: "path-step-body" },
      el("div", { class: "path-step-text" },
        el("span", { class: "path-step-title", text: m.title }),
        m.summary ? el("span", { class: "path-step-what", text: m.summary }) : null,
        el("span", { class: "path-step-sub", text: sub })),
      action));
}


/* ---------- Practice home ---------- */
// One obvious next step, then reviews, paths and struggles (docs/PEDAGOGY.md: spacing first,
// autonomy through choice, no guilt about missed days).
async function loadHome() {
  const [prog, paths] = await Promise.all([api("/api/progress"), api("/api/paths"), loadTracks()]);
  state.paths = paths;
  const q = prog.questions;
  const w = prog.week;
  $("#home-lede").textContent = `${w.this_week} of ${w.target} practice days this week. `
    + (w.streak ? `Weekly streak: ${plural(w.streak, "week")}${w.repaired ? ", with one missed week forgiven" : ""}.`
      : w.sessions ? `${plural(w.sessions, "practice day")} so far.` : `A week counts toward your streak at ${w.target} practice days.`);

  const today = isoDay(new Date());
  const sections = [];
  const setup = setupSteps(prog, paths);
  if (setup.some((st) => !st.done)) sections.push(homeSection("Get started", el("ol", { class: "setup" }, setup.map(setupItem))));

  const open = q.filter((r) => r.status === "attempted").sort((a, b) => b.last_run.created_at.localeCompare(a.last_run.created_at));
  const fresh = q.find((r) => r.status === "new");
  const next = open[0] || fresh;
  if (next) {
    const sub = next.last_run
      ? `Last run ${shortDate(next.last_run.created_at)}: ${next.last_run.passed} of ${next.last_run.total} tests passed.`
      : "Not started yet.";
    sections.push(homeSection(open[0] ? "Pick up where you left off" : "Start here",
      el("ul", { class: "home-list" }, homeRow(next.title, `${moduleTitle(next.module)}. ${sub}`,
        el("a", { class: "btn btn-primary", href: `#/${next.key}` }, open[0] ? "Continue" : "Start")))));
  }

  const due = q.filter((r) => r.review_due && r.review_due <= today).slice(0, 3);
  if (due.length) {
    sections.push(homeSection("Due for review", el("ul", { class: "home-list" }, due.map((r) => homeRow(r.title,
      `${r.solve === "assisted" ? "Solved with help" : "Solved"} on ${shortDate(r.solved_at)}. A fresh variant checks it stuck. Ask your agent:`,
      askLine(`Build a Whetstone variant of ${r.key} for review.`))))));
  }

  const started = paths.filter((p) => p.mine || pathStats(p).solved).slice(0, 3);
  const steps = started.map((p) => [p, p.modules.find((m) => !m.built || m.solved < m.questions)]).filter(([, m]) => m);
  if (steps.length) {
    sections.push(homeSection("Next in your paths", el("ul", { class: "home-list" }, steps.map(([p, m]) => homeRow(p.title,
      m.built ? `${m.title}: ${m.solved} of ${plural(m.questions, "question")} solved.` : `${m.title} is not built yet. Ask your agent:`,
      m.built ? el("a", { class: "btn btn-secondary", href: `#/${m.module}/${m.next}` }, m.solved ? "Continue" : "Start")
        : askLine(`Build the first Whetstone question for the ${m.module} module.`))))));
  }

  const stuck = q.filter((r) => r !== next && r.status === "attempted" && (r.runs >= 5 || r.hints_opened >= 2)).slice(0, 3);
  if (stuck.length) {
    sections.push(homeSection("Where you struggled", el("ul", { class: "home-list" }, stuck.map((r) => homeRow(r.title,
      `${plural(r.runs, "run")}, ${r.hints_opened} of ${r.hint_count} hints. Your agent can guide you without giving it away:`,
      askLine(`I'm stuck on ${r.key}.`))))));
  }

  const days = el("div", { class: "days", role: "img" });
  fillDays(days, prog.active_days);
  sections.push(homeSection("Last 4 weeks", days));
  $("#home-body").replaceChildren(...sections);
}

function moduleTitle(id) { return (state.tracks.find((t) => t.id === id) || { title: id }).title; }

function setupSteps(prog, paths) {
  return [
    { done: prog.has_profile, title: "Set up your profile", sub: "Your agent writes it from what it knows about you, plus a few questions.", ask: "Set up my Whetstone profile." },
    { done: paths.some((p) => p.mine) || prog.questions.length > 0, title: "Pick a system to build", sub: "Browse the Paths page, or ask your agent for one.", link: "#/paths" },
    { done: prog.questions.length > 0, title: "Build your first question", sub: "Your agent writes it and Whetstone checks it.", ask: "Build the first Whetstone question for my path." },
    { done: prog.questions.some((r) => r.status === "solved"), title: "Solve it", sub: "Run the tests as you go, then Submit." },
  ];
}

function setupItem(st) {
  return el("li", { class: "setup-step", "data-done": st.done ? "true" : "false" },
    el("span", { class: "setup-title", text: st.title }),
    st.done ? null : el("span", { class: "home-sub", text: st.sub }),
    st.done ? null : st.ask ? askLine(st.ask) : st.link ? el("a", { class: "btn btn-secondary", href: st.link }, "Open Paths") : null);
}

function homeSection(title, body) {
  return el("section", { class: "home-section" }, el("h2", { text: title }), body);
}

function homeRow(title, sub, action) {
  return el("li", { class: "home-row" },
    el("span", { class: "home-text" }, el("span", { class: "home-title", text: title }), el("span", { class: "home-sub", text: sub })),
    action);
}

function askLine(text) {
  const copy = el("button", { type: "button", class: "btn btn-quiet", onclick: () => copyText(text, copy) }, "Copy");
  return el("p", { class: "ask-line" }, el("code", { text }), copy);
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

async function route() {
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
  document.title = "Practice · Whetstone";
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

  const [config] = await Promise.all([api("/api/config"), initEditor(), loadTracks()]);
  state.config = config;
  await loadStats();
  window.addEventListener("hashchange", route);
  await route();
}

boot().catch((err) => {
  showView("practice");
  $("#challenge-title").textContent = "Whetstone could not start";
  $("#panel-lesson").textContent = err.message;
});
