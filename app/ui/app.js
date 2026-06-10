"use strict";
/* ════════════════════════════════════════════════════════════════════
   GimmeTools v2 — application logic.
   Vanilla JS, no build step. Talks to Python through window.pywebview.api;
   falls back to a mock in a plain browser so the UI can be developed and
   previewed without the shell.
   ════════════════════════════════════════════════════════════════════ */

/* ── tiny DOM helpers ──────────────────────────────────────────────── */

const $ = (sel) => document.querySelector(sel);

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k === "html") node.innerHTML = v;       // trusted markup only
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined) node.setAttribute(k, v);
  }
  for (const c of [].concat(children)) {
    if (c) node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return node;
}

function svgIcon(pathData, size = 16) {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24");
  s.style.width = s.style.height = size + "px";
  const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
  p.setAttribute("d", pathData);
  s.appendChild(p);
  return s;
}

const ICON = {
  star: "M12 2l2.9 6.2 6.6.8-4.9 4.6 1.3 6.5L12 16.9 6.1 20.1l1.3-6.5L2.5 9l6.6-.8L12 2z",
  drop: "M12 3v12m0 0l-4-4m4 4l4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2",
  play: "M6 4l14 8-14 8V4z",
  check: "M4 12.5l5 5L20 6.5",
  x: "M5 5l14 14M19 5L5 19",
  clock: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zm0 4v5l3.5 2",
  up: "M12 19V5m0 0l-6 6m6-6l6 6",
  down: "M12 5v14m0 0l-6-6m6 6l6-6",
  gear: "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
  bolt: "M13 2L4 14h6l-1 8 9-12h-6l1-8z",
};

function fmtDuration(s) {
  if (s == null || isNaN(s)) return "";
  s = Math.round(s);
  if (s < 60) return s + "s";
  return Math.floor(s / 60) + "m " + (s % 60) + "s";
}

function fmtAgo(ts) {
  if (!ts) return "";
  const d = Date.now() / 1000 - ts;
  if (d < 60) return "just now";
  if (d < 3600) return Math.floor(d / 60) + "m ago";
  if (d < 86400) return Math.floor(d / 3600) + "h ago";
  return Math.floor(d / 86400) + "d ago";
}

/* ── API bridge (pywebview, or mock in a plain browser) ────────────── */

const api = {
  _ready: null,

  ready() {
    if (this._ready) return this._ready;
    this._ready = new Promise((resolve) => {
      if (window.pywebview && window.pywebview.api) return resolve(false);
      let settled = false;
      window.addEventListener("pywebviewready", () => { settled = true; resolve(false); });
      setTimeout(() => { if (!settled) resolve(true); }, 1200);   // → mock
    });
    return this._ready;
  },

  async call(name, ...args) {
    const useMock = await this.ready();
    if (!useMock) return window.pywebview.api[name](...args);
    return mockApi(name, ...args);
  },
};

/* Browser-preview mock — enough state to render and click around. */
const MOCK = {
  boot: {
    version: "2.0", root: "D:\\GimmeTools", venv_ok: true,
    favorites: ["upscale"], recents: ["remove-bg", "upscale"],
    settings: { output_dir: null, keep_intermediate: false, check_updates: true },
    presets: [{ id: "p1", tool_id: "upscale", name: "Anime 2x",
                options: { model: "realesr-animevideov3", scale: "2" }, updated: 0 }],
    tools: [
      { id: "remove-bg", name: "Remove Background", category: "Image",
        description: "Cut the background out of any image — transparent PNG out.",
        icon: "M9.5 2.7l1 2.3 2.3 1-2.3 1-1 2.3-1-2.3L6.2 6l2.3-1 1-2.3z", accepts: "image",
        options: [
          { key: "model", label: "Model", kind: "select", choices: ["birefnet-general", "u2net"], default: "birefnet-general", help: "" },
          { key: "gpu", label: "GPU", kind: "select", choices: ["auto", "cpu"], default: "auto", help: "" }],
        keywords: [], constraints: {} },
      { id: "upscale", name: "Upscale Image", category: "Image",
        description: "Enlarge images 2-4x with Real-ESRGAN.", icon: "M3 9V5a2 2 0 0 1 2-2h4",
        accepts: "image",
        options: [
          { key: "model", label: "Model", kind: "select", choices: ["realesrgan-x4plus", "realesr-animevideov3"], default: "realesrgan-x4plus", help: "" },
          { key: "scale", label: "Scale", kind: "select", choices: ["2", "3", "4"], default: "4", help: "" }],
        keywords: [], constraints: { scale: { "realesrgan-x4plus": ["4"], "realesr-animevideov3": ["2", "3", "4"] } } },
      { id: "process-video", name: "Process Video", category: "Video",
        description: "Topaz enhance then H.265 encode.", icon: "M4 3h16", accepts: "video",
        options: [{ key: "skip_topaz", label: "Skip Topaz", kind: "toggle", default: false, help: "" }],
        keywords: [], constraints: {} },
      { id: "diagnose", name: "Diagnostics", category: "System",
        description: "Check every dependency, GPU, model, and folder.", icon: "M3 12h4l2-7 4 14 2-7h6",
        accepts: "none", options: [], keywords: [], constraints: {} },
    ],
    state: { paused: false, current: null, queue: [], history: [
      { id: "h1", tool_id: "upscale", tool_name: "Upscale Image", label: "photo.jpg",
        status: "done", created: Date.now() / 1000 - 700, started: Date.now() / 1000 - 690,
        ended: Date.now() / 1000 - 660, exit_code: 0, progress_cur: 0, progress_total: 0 }] },
  },
};

function mockApi(name, ...args) {
  switch (name) {
    case "boot": return MOCK.boot;
    case "get_state": return MOCK.boot.state;
    case "get_last_options": return {};
    case "toggle_favorite": {
      const f = MOCK.boot.favorites, id = args[0];
      f.includes(id) ? f.splice(f.indexOf(id), 1) : f.push(id);
      return [...f];
    }
    case "enqueue": return { ok: true, job_id: "mock", recents: MOCK.boot.recents };
    case "get_settings": return MOCK.boot.settings;
    case "save_settings": return Object.assign(MOCK.boot.settings, args[0]);
    case "save_preset": return { ok: true, presets: MOCK.boot.presets };
    case "check_updates": return { available: false, current: "2.0", latest: "", url: "" };
    case "pick_files": case "pick_folder": return [];
    case "get_job_log": return ["[mock] log line"];
    default: return null;
  }
}

/* ── State ─────────────────────────────────────────────────────────── */

const S = {
  boot: null,
  tools: [],
  currentToolId: null,
  inputs: [],               // selected file/folder paths
  options: {},              // current option values for current tool
  presets: [],
  favorites: [],
  recents: [],
  queueState: { paused: false, current: null, queue: [], history: [] },
  activeTab: "queue",
  logJobId: null,
  pollTimer: null,
  seenJobs: new Set(),      // history ids already toasted
};

/* ── Boot ──────────────────────────────────────────────────────────── */

async function boot() {
  S.boot = await api.call("boot");
  S.tools = S.boot.tools;
  S.favorites = S.boot.favorites;
  S.recents = S.boot.recents;
  S.presets = S.boot.presets;
  S.queueState = S.boot.state;
  for (const h of S.queueState.history) S.seenJobs.add(h.id);
  S.currentToolId = S.recents[0] || S.tools[0].id;

  $("#setup-banner").classList.toggle("hidden", S.boot.venv_ok);
  renderNav();
  await selectTool(S.currentToolId);
  renderActivity();
  schedulePoll();
}

/* ── Sidebar nav ───────────────────────────────────────────────────── */

function renderNav() {
  const nav = $("#nav");
  nav.replaceChildren();

  const mkItem = (tool) => {
    const star = svgIcon(ICON.star, 13);
    star.classList.add("star");
    if (S.favorites.includes(tool.id)) star.classList.add("faved");
    star.addEventListener("click", async (e) => {
      e.stopPropagation();
      S.favorites = await api.call("toggle_favorite", tool.id);
      renderNav();
      renderToolHead();
    });
    const item = el("button", {
      class: "nav-item" + (tool.id === S.currentToolId ? " active" : ""),
      onclick: () => selectTool(tool.id),
    }, [svgIcon(tool.icon), el("span", { text: tool.name }), star]);
    return item;
  };

  const favs = S.tools.filter((t) => S.favorites.includes(t.id));
  if (favs.length) {
    nav.appendChild(el("div", { class: "nav-section", text: "Favorites" }));
    favs.forEach((t) => nav.appendChild(mkItem(t)));
  }

  for (const cat of ["Image", "Video", "System"]) {
    const tools = S.tools.filter((t) => t.category === cat);
    if (!tools.length) continue;
    nav.appendChild(el("div", { class: "nav-section", text: cat }));
    tools.forEach((t) => nav.appendChild(mkItem(t)));
  }

  const recents = S.recents
    .map((id) => S.tools.find((t) => t.id === id))
    .filter((t) => t && !S.favorites.includes(t.id))
    .slice(0, 3);
  if (recents.length) {
    nav.appendChild(el("div", { class: "nav-section", text: "Recent" }));
    recents.forEach((t) => nav.appendChild(mkItem(t)));
  }
}

/* ── Tool view ─────────────────────────────────────────────────────── */

function currentTool() {
  return S.tools.find((t) => t.id === S.currentToolId);
}

async function selectTool(toolId) {
  S.currentToolId = toolId;
  S.inputs = [];
  const tool = currentTool();
  const last = await api.call("get_last_options", toolId);
  S.options = {};
  for (const opt of tool.options) {
    S.options[opt.key] = last[opt.key] !== undefined ? last[opt.key] : opt.default;
  }
  renderNav();
  renderToolView();
}

function renderToolHead() {
  const tool = currentTool();
  const fav = $("#fav-btn");
  if (fav) fav.classList.toggle("faved", S.favorites.includes(tool.id));
}

function renderToolView() {
  const tool = currentTool();
  const view = $("#tool-view");
  view.replaceChildren();

  /* header */
  const favBtn = el("button", {
    class: "fav-btn" + (S.favorites.includes(tool.id) ? " faved" : ""),
    id: "fav-btn", title: "Favorite",
    onclick: async () => {
      S.favorites = await api.call("toggle_favorite", tool.id);
      renderNav(); renderToolHead();
    },
  }, [svgIcon(ICON.star, 17)]);

  const iconBox = el("div", { class: "tool-icon" }, [svgIcon(tool.icon, 22)]);
  view.appendChild(el("div", { class: "tool-head" }, [
    iconBox,
    el("div", { class: "tool-title-wrap" }, [
      el("div", { class: "tool-title" }, [tool.name, favBtn]),
      el("div", { class: "tool-desc", text: tool.description }),
    ]),
  ]));

  /* presets */
  if (tool.options.length) view.appendChild(buildPresetRow(tool));

  /* inputs */
  if (tool.accepts !== "none") {
    view.appendChild(buildDropzone(tool));
    view.appendChild(el("div", { class: "file-chips", id: "file-chips" }));
    renderChips();
  }

  /* options */
  if (tool.options.length) {
    const grid = el("div", { class: "options-grid", id: "options-grid" });
    view.appendChild(grid);
    renderOptions(tool, grid);
  }

  /* run bar */
  const runBtn = el("button", { class: "btn btn-primary btn-lg", id: "run-btn", onclick: runCurrent },
    [svgIcon(ICON.play, 14), tool.accepts === "none" ? "Run diagnostics" : "Run", el("kbd", { text: "Ctrl ↵" })]);
  view.appendChild(el("div", { class: "run-bar" }, [runBtn]));
}

/* options form, honoring registry constraints */
function renderOptions(tool, grid) {
  grid.replaceChildren();
  for (const opt of tool.options) {
    if (opt.kind === "toggle") {
      const input = el("input", { type: "checkbox" });
      input.checked = !!S.options[opt.key];
      input.addEventListener("change", () => { S.options[opt.key] = input.checked; });
      grid.appendChild(el("div", { class: "field" }, [
        el("label", { class: "toggle" }, [input, el("span", { class: "track" }),
          el("span", { text: opt.label })]),
        opt.help ? el("div", { class: "field-help", text: opt.help }) : null,
      ]));
      continue;
    }

    const select = el("select", { "data-key": opt.key });
    const allowed = allowedChoices(tool, opt);
    for (const c of allowed) select.appendChild(el("option", { value: c, text: c }));
    if (!allowed.includes(String(S.options[opt.key]))) S.options[opt.key] = allowed[0];
    select.value = S.options[opt.key];
    select.disabled = allowed.length === 1 && opt.choices.length > 1;
    select.addEventListener("change", () => {
      S.options[opt.key] = select.value;
      renderOptions(tool, grid);          // re-evaluate constraints
    });
    grid.appendChild(el("div", { class: "field" }, [
      el("span", { class: "field-label", text: opt.label }),
      select,
      opt.help ? el("div", { class: "field-help", text: opt.help }) : null,
    ]));
  }
}

function allowedChoices(tool, opt) {
  const rules = tool.constraints && tool.constraints[opt.key];
  if (!rules) return opt.choices;
  for (const [controllerKey, mapping] of Object.entries(groupConstraints(tool))) {
    if (!(opt.key in mapping)) continue;
    const controllerVal = String(S.options[controllerKey]);
    const allowed = mapping[opt.key][controllerVal];
    if (allowed) return allowed;
  }
  // constraints keyed by another option's value: {scale: {modelValue: [..]}}
  const byValue = rules[String(findControllerValue(tool, opt.key))];
  return byValue || opt.choices;
}

/* constraints are stored as {dependentKey: {controllingValue: allowed[]}};
   the controlling option is whichever option has those values as choices */
function findControllerValue(tool, dependentKey) {
  const rules = tool.constraints[dependentKey];
  const controllingValues = Object.keys(rules);
  for (const opt of tool.options) {
    if (opt.key === dependentKey) continue;
    if (opt.choices.some((c) => controllingValues.includes(String(c)))) {
      return S.options[opt.key];
    }
  }
  return null;
}

function groupConstraints() { return {}; }   // single-level constraints only

/* ── Presets ───────────────────────────────────────────────────────── */

function buildPresetRow(tool) {
  const row = el("div", { class: "preset-row" });
  row.appendChild(el("label", { text: "Preset" }));

  const select = el("select", { style: "width:200px" });
  select.appendChild(el("option", { value: "", text: "Last used" }));
  for (const p of S.presets.filter((p) => p.tool_id === tool.id)) {
    select.appendChild(el("option", { value: p.id, text: p.name }));
  }
  select.addEventListener("change", () => {
    const p = S.presets.find((x) => x.id === select.value);
    if (p) {
      S.options = Object.assign({}, S.options, p.options);
      renderOptions(tool, $("#options-grid"));
      toast("Preset “" + p.name + "” applied", "ok");
    }
    delBtn.disabled = !p;
  });
  row.appendChild(select);

  row.appendChild(el("button", {
    class: "btn btn-sm", text: "Save preset…",
    onclick: () => askText("Save preset", "Name this preset:", async (name) => {
      const res = await api.call("save_preset", tool.id, name, S.options);
      if (res.ok) { S.presets = res.presets; renderToolView(); toast("Preset saved", "ok"); }
      else toast(res.error || "Could not save preset", "err");
    }),
  }));

  const delBtn = el("button", {
    class: "btn btn-ghost btn-sm", text: "Delete", disabled: "true",
    onclick: () => {
      const p = S.presets.find((x) => x.id === select.value);
      if (!p) return;
      confirmDialog("Delete preset", "Delete “" + p.name + "”?", async () => {
        const res = await api.call("delete_preset", p.id);
        S.presets = res.presets;
        renderToolView();
      });
    },
  });
  delBtn.disabled = true;
  row.appendChild(delBtn);
  return row;
}

/* ── Inputs: dropzone + chips ──────────────────────────────────────── */

function buildDropzone(tool) {
  const kindLabel = tool.accepts === "image" ? "images" : "videos";
  const dz = el("div", { class: "dropzone", id: "dropzone" }, [
    svgIcon(ICON.drop, 26),
    el("div", { text: "Drop " + kindLabel + " or a folder here" }),
    el("div", { class: "dz-hint", text: "Folders run as a batch · multiple files queue as separate jobs" }),
    el("div", { class: "dz-buttons" }, [
      el("button", { class: "btn btn-sm", text: "Browse files…", onclick: async (e) => {
        e.stopPropagation();
        const files = await api.call("pick_files", tool.accepts);
        addInputs(files);
      } }),
      el("button", { class: "btn btn-sm", text: "Choose folder…", onclick: async (e) => {
        e.stopPropagation();
        const folder = await api.call("pick_folder");
        addInputs(folder);
      } }),
    ]),
  ]);

  dz.addEventListener("click", async () => {
    const files = await api.call("pick_files", tool.accepts);
    addInputs(files);
  });
  dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("dragover"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("dragover"));
  dz.addEventListener("drop", (e) => {
    e.preventDefault();
    dz.classList.remove("dragover");
    const paths = [];
    for (const f of e.dataTransfer.files) {
      const p = f.pywebviewFullPath || f.path;
      if (p) paths.push(p);
    }
    if (!paths.length) {
      toast("Could not read dropped paths — use Browse instead", "warn");
      return;
    }
    addInputs(paths);
  });
  return dz;
}

function addInputs(paths) {
  if (!paths || !paths.length) return;
  for (const p of paths) if (!S.inputs.includes(p)) S.inputs.push(p);
  renderChips();
}

function renderChips() {
  const wrap = $("#file-chips");
  if (!wrap) return;
  wrap.replaceChildren();
  S.inputs.forEach((p, i) => {
    const name = p.replace(/[\\/]+$/, "").split(/[\\/]/).pop();
    wrap.appendChild(el("span", { class: "chip", title: p }, [
      el("span", { text: name }),
      el("button", { text: "×", title: "Remove", onclick: () => {
        S.inputs.splice(i, 1); renderChips();
      } }),
    ]));
  });
}

/* ── Run ───────────────────────────────────────────────────────────── */

async function runCurrent() {
  const tool = currentTool();
  if (tool.accepts !== "none" && !S.inputs.length) {
    toast("Add a file or folder first", "warn");
    return;
  }
  const inputs = tool.accepts === "none" ? [[]] : S.inputs.map((p) => [p]);
  let queued = 0;
  for (const inp of inputs) {
    const res = await api.call("enqueue", tool.id, inp, S.options);
    if (res.ok) { queued++; S.recents = res.recents || S.recents; }
    else toast(res.error || "Could not queue job", "err");
  }
  if (queued) {
    toast(queued === 1 ? "Job queued" : queued + " jobs queued", "ok");
    S.inputs = [];
    renderChips();
    renderNav();
    refreshState(true);
  }
}

/* ── Activity panel (queue / history / log) ────────────────────────── */

function statusIcon(status) {
  const box = el("span", { class: "job-status" });
  if (status === "running") { box.appendChild(el("span", { class: "spinner" })); return box; }
  let icon = ICON.clock, cls = "muted";
  if (status === "done") { icon = ICON.check; cls = "ok"; }
  if (status === "failed") { icon = ICON.x; cls = "err"; }
  if (status === "cancelled") { icon = ICON.x; cls = "muted"; }
  const s = svgIcon(icon, 13);
  s.classList.add(cls);
  box.appendChild(s);
  return box;
}

function renderActivity() {
  renderQueuePanel();
  renderHistoryPanel();
  renderLogPanel();
  renderQueuePill();

  const st = S.queueState;
  $("#pause-btn").textContent = st.paused ? "Resume queue" : "Pause queue";
  const n = st.queue.length + (st.current ? 1 : 0);
  $("#tab-queue-count").textContent = n ? String(n) : "";
}

function renderQueuePanel() {
  const panel = $("#panel-queue");
  panel.replaceChildren();
  const st = S.queueState;

  if (!st.current && !st.queue.length) {
    panel.appendChild(el("div", { class: "empty-panel", text: "Nothing queued — drop some files in." }));
    return;
  }

  if (st.current) {
    const j = st.current;
    const pct = j.progress_total ? (100 * j.progress_cur / j.progress_total) : null;
    const bar = el("div", { class: "progress" + (pct === null ? " indeterminate" : "") },
      [el("div", { style: "width:" + (pct === null ? 30 : pct) + "%" })]);
    panel.appendChild(el("div", { class: "job-row", onclick: () => showLog(j.id) }, [
      statusIcon("running"),
      el("span", { class: "job-label", text: j.label }),
      el("span", { class: "job-tool", text: j.tool_name }),
      bar,
      el("span", { class: "job-meta", text: j.progress_total ? (j.progress_cur + "/" + j.progress_total) : "running" }),
      el("span", { class: "job-actions" }, [
        el("button", { class: "icon-btn", title: "Cancel", text: "✕", onclick: (e) => {
          e.stopPropagation(); cancelJob(j.id);
        } }),
      ]),
    ]));
  }

  st.queue.forEach((j, i) => {
    panel.appendChild(el("div", { class: "job-row" }, [
      statusIcon("queued"),
      el("span", { class: "job-label", text: j.label }),
      el("span", { class: "job-tool", text: j.tool_name }),
      el("span", { class: "job-meta", text: "#" + (i + 1) }),
      el("span", { class: "job-actions" }, [
        el("button", { class: "icon-btn", title: "Move up", html: "↑", onclick: async () => {
          await api.call("move_job", j.id, -1); refreshState(true);
        } }),
        el("button", { class: "icon-btn", title: "Move down", html: "↓", onclick: async () => {
          await api.call("move_job", j.id, 1); refreshState(true);
        } }),
        el("button", { class: "icon-btn", title: "Remove", text: "✕", onclick: () => cancelJob(j.id) }),
      ]),
    ]));
  });
}

function renderHistoryPanel() {
  const panel = $("#panel-history");
  panel.replaceChildren();
  const items = S.queueState.history;
  if (!items.length) {
    panel.appendChild(el("div", { class: "empty-panel", text: "No finished jobs yet." }));
    return;
  }
  for (const j of items) {
    const dur = j.started && j.ended ? fmtDuration(j.ended - j.started) : "";
    panel.appendChild(el("div", { class: "job-row", onclick: () => showLog(j.id) }, [
      statusIcon(j.status),
      el("span", { class: "job-label", text: j.label }),
      el("span", { class: "job-tool", text: j.tool_name }),
      el("span", { class: "job-meta", text: [dur, fmtAgo(j.ended)].filter(Boolean).join(" · ") }),
    ]));
  }
}

async function renderLogPanel() {
  const pre = $("#log-pre");
  if (S.activeTab !== "log") return;
  if (!S.logJobId) { pre.textContent = "Select a job in Queue or History to see its log."; return; }
  const cur = S.queueState.current;
  const lines = (cur && cur.id === S.logJobId)
    ? cur.log
    : await api.call("get_job_log", S.logJobId);
  const atBottom = pre.scrollHeight - pre.scrollTop - pre.clientHeight < 60;
  pre.textContent = (lines || []).join("\n") || "(no output yet)";
  if (atBottom) pre.scrollTop = pre.scrollHeight;
}

function renderQueuePill() {
  const st = S.queueState;
  const dot = $("#queue-dot");
  dot.className = "dot" + (st.paused ? " paused" : (st.current || st.queue.length ? " busy" : ""));
  const n = st.queue.length + (st.current ? 1 : 0);
  $("#queue-summary").textContent =
    st.paused ? "Paused" : st.current ? (st.current.tool_name + "…") : n ? n + " queued" : "Idle";
}

function showLog(jobId) {
  S.logJobId = jobId;
  switchTab("log");
}

function cancelJob(jobId) {
  confirmDialog("Cancel job", "Stop this job?", async () => {
    await api.call("cancel_job", jobId);
    refreshState(true);
  });
}

function switchTab(name) {
  S.activeTab = name;
  document.querySelectorAll(".tab").forEach((t) =>
    t.classList.toggle("active", t.dataset.tab === name));
  $("#panel-queue").classList.toggle("hidden", name !== "queue");
  $("#panel-history").classList.toggle("hidden", name !== "history");
  $("#panel-log").classList.toggle("hidden", name !== "log");
  $("#clear-history-btn").classList.toggle("hidden", name !== "history");
  renderActivity();
}

/* ── Polling ───────────────────────────────────────────────────────── */

async function refreshState(immediate = false) {
  const st = await api.call("get_state");
  const prevSetupRunning =
    S.queueState.current && S.queueState.current.tool_id === "setup";
  S.queueState = st;

  for (const h of st.history) {
    if (!S.seenJobs.has(h.id)) {
      S.seenJobs.add(h.id);
      if (h.status === "done") toast(h.label + " — done", "ok");
      else if (h.status === "failed") {
        toast(h.label + " — failed", "err", "View log", () => showLog(h.id));
      }
      if (h.tool_id === "setup" && h.status === "done") boot();   // venv now exists
    }
  }
  renderActivity();
  if (immediate) schedulePoll();
}

function schedulePoll() {
  clearTimeout(S.pollTimer);
  const active = S.queueState.current || S.queueState.queue.length;
  if (!active) return;          // actions trigger refresh; idle = no polling
  S.pollTimer = setTimeout(async () => { await refreshState(); schedulePoll(); }, 700);
}

/* ── Command palette ───────────────────────────────────────────────── */

const palette = {
  open: false,
  items: [],
  selected: 0,

  buildItems() {
    const items = S.tools.map((t) => ({
      icon: t.icon, label: t.name, cat: t.category,
      keywords: (t.keywords || []).join(" "),
      run: () => selectTool(t.id),
    }));
    const st = S.queueState;
    items.push(
      { icon: ICON.clock, label: st.paused ? "Resume queue" : "Pause queue", cat: "Queue",
        keywords: "pause resume hold", run: () => togglePause() },
      { icon: ICON.gear, label: "Open Settings", cat: "App", keywords: "preferences config",
        run: () => openSettings() },
      { icon: ICON.bolt, label: "Check for updates", cat: "App", keywords: "version upgrade",
        run: () => manualUpdateCheck() },
      { icon: ICON.drop, label: "Import presets…", cat: "Presets", keywords: "load",
        run: async () => {
          const res = await api.call("import_presets");
          if (res.ok) { S.presets = res.presets; renderToolView(); toast(res.count + " presets imported", "ok"); }
          else if (res.error !== "cancelled") toast(res.error, "err");
        } },
      { icon: ICON.up, label: "Export presets…", cat: "Presets", keywords: "save share",
        run: async () => {
          const res = await api.call("export_presets", null);
          if (res.ok) toast(res.count + " presets exported", "ok");
          else if (res.error !== "cancelled") toast(res.error, "err");
        } },
      { icon: ICON.x, label: "Clear job history", cat: "Queue", keywords: "delete",
        run: () => confirmDialog("Clear history", "Remove all finished jobs from history?",
          async () => { await api.call("clear_history"); refreshState(true); }) },
      { icon: ICON.drop, label: "Open output folder", cat: "App", keywords: "explorer results",
        run: async () => {
          const s = await api.call("get_settings");
          await api.call("open_path", s.output_dir || (S.boot.root + "\\outputs"));
        } },
    );
    return items;
  },

  show() {
    this.open = true;
    this.items = this.buildItems();
    this.selected = 0;
    $("#palette").classList.remove("hidden");
    const input = $("#palette-input");
    input.value = "";
    input.focus();
    this.render("");
  },

  hide() {
    this.open = false;
    $("#palette").classList.add("hidden");
  },

  match(query) {
    if (!query) return this.items;
    const q = query.toLowerCase();
    return this.items
      .map((item) => {
        const hay = (item.label + " " + item.keywords).toLowerCase();
        let score = -1;
        if (hay.startsWith(q)) score = 0;
        else if (hay.includes(" " + q)) score = 1;
        else if (hay.includes(q)) score = 2;
        else {
          // subsequence
          let i = 0;
          for (const ch of hay) if (ch === q[i]) i++;
          if (i === q.length) score = 3;
        }
        return { item, score };
      })
      .filter((x) => x.score >= 0)
      .sort((a, b) => a.score - b.score)
      .map((x) => x.item);
  },

  render(query) {
    const wrap = $("#palette-results");
    wrap.replaceChildren();
    const matches = this.match(query);
    if (!matches.length) {
      wrap.appendChild(el("div", { class: "palette-empty", text: "No matches." }));
      return;
    }
    this.matches = matches;
    if (this.selected >= matches.length) this.selected = 0;
    matches.forEach((item, i) => {
      const node = el("div", {
        class: "palette-item" + (i === this.selected ? " selected" : ""),
        onclick: () => { this.hide(); item.run(); },
        onmousemove: () => { this.selected = i; this.render($("#palette-input").value); },
      }, [svgIcon(item.icon), el("span", { text: item.label }),
          el("span", { class: "pi-cat", text: item.cat })]);
      wrap.appendChild(node);
    });
  },

  key(e) {
    const matches = this.matches || this.items;
    if (e.key === "ArrowDown") { e.preventDefault(); this.selected = (this.selected + 1) % matches.length; }
    else if (e.key === "ArrowUp") { e.preventDefault(); this.selected = (this.selected - 1 + matches.length) % matches.length; }
    else if (e.key === "Enter") {
      const item = matches[this.selected];
      if (item) { this.hide(); item.run(); }
      return;
    } else return;
    this.render($("#palette-input").value);
  },
};

/* ── Toasts ────────────────────────────────────────────────────────── */

function toast(message, kind = "", actionLabel = null, action = null) {
  const wrap = $("#toasts");
  const node = el("div", { class: "toast " + kind }, [
    el("span", { text: message }),
    actionLabel ? el("button", { text: actionLabel, onclick: () => { action(); dismiss(); } }) : null,
  ]);
  wrap.appendChild(node);
  const dismiss = () => {
    node.classList.add("leaving");
    setTimeout(() => node.remove(), 220);
  };
  setTimeout(dismiss, actionLabel ? 8000 : 4000);
}

/* ── Dialogs ───────────────────────────────────────────────────────── */

let dialogInput = null;

function confirmDialog(title, text, onOk) {
  $("#dialog-title").textContent = title;
  $("#dialog-text").textContent = text;
  if (dialogInput) { dialogInput.remove(); dialogInput = null; }
  openDialog(onOk);
}

function askText(title, text, onOk) {
  $("#dialog-title").textContent = title;
  $("#dialog-text").textContent = text;
  if (dialogInput) dialogInput.remove();
  dialogInput = el("input", { type: "text", style: "margin-top:10px" });
  $("#dialog-text").after(dialogInput);
  openDialog(() => {
    const v = dialogInput.value.trim();
    if (v) onOk(v);
  });
  setTimeout(() => dialogInput.focus(), 50);
}

function openDialog(onOk) {
  const overlay = $("#dialog");
  overlay.classList.remove("hidden");
  const ok = $("#dialog-ok"), cancel = $("#dialog-cancel");
  const close = () => { overlay.classList.add("hidden"); ok.onclick = cancel.onclick = null; };
  ok.onclick = () => { close(); onOk(); };
  cancel.onclick = close;
}

/* ── Settings ──────────────────────────────────────────────────────── */

async function openSettings() {
  const body = $("#settings-body");
  const settings = await api.call("get_settings");
  body.replaceChildren();

  /* output */
  const outInput = el("input", { type: "text", class: "grow", placeholder: "Same folder as input (default)" });
  outInput.value = settings.output_dir || "";
  outInput.readOnly = true;
  body.appendChild(el("div", { class: "settings-group" }, [
    el("h3", { text: "Output" }),
    el("div", { class: "settings-row" }, [
      outInput,
      el("button", { class: "btn btn-sm", text: "Browse…", onclick: async () => {
        const r = await api.call("pick_folder");
        if (r && r.length) { outInput.value = r[0]; save({ output_dir: r[0] }); }
      } }),
      el("button", { class: "btn btn-ghost btn-sm", text: "Reset", onclick: () => {
        outInput.value = ""; save({ output_dir: null });
      } }),
    ]),
    el("div", { class: "settings-note", text: "Where processed files are written. Default keeps them next to the originals." }),
  ]));

  /* toggles */
  const mkToggle = (label, key, value) => {
    const input = el("input", { type: "checkbox" });
    input.checked = !!value;
    input.addEventListener("change", () => save({ [key]: input.checked }));
    return el("label", { class: "toggle" }, [input, el("span", { class: "track" }), el("span", { text: label })]);
  };
  body.appendChild(el("div", { class: "settings-group" }, [
    el("h3", { text: "Behavior" }),
    mkToggle("Keep intermediate video files (debugging)", "keep_intermediate", settings.keep_intermediate),
    mkToggle("Check for updates at startup", "check_updates", settings.check_updates),
  ]));

  /* presets */
  body.appendChild(el("div", { class: "settings-group" }, [
    el("h3", { text: "Presets" }),
    el("div", { class: "settings-row" }, [
      el("button", { class: "btn btn-sm", text: "Import…", onclick: async () => {
        const res = await api.call("import_presets");
        if (res.ok) { S.presets = res.presets; renderToolView(); toast(res.count + " presets imported", "ok"); }
        else if (res.error !== "cancelled") toast(res.error, "err");
      } }),
      el("button", { class: "btn btn-sm", text: "Export all…", onclick: async () => {
        const res = await api.call("export_presets", null);
        if (res.ok) toast(res.count + " presets exported", "ok");
        else if (res.error !== "cancelled") toast(res.error, "err");
      } }),
    ]),
  ]));

  /* shortcuts */
  const KEYS = [["Ctrl K", "Command palette"], ["Ctrl ↵", "Run current tool"],
                ["Ctrl ,", "Settings"], ["Ctrl 1–4", "Switch tools"], ["Esc", "Close dialogs"]];
  body.appendChild(el("div", { class: "settings-group" },
    [el("h3", { text: "Keyboard shortcuts" })].concat(
      KEYS.map(([k, d]) => el("div", { class: "kbd-row" },
        [el("span", { text: d }), el("kbd", { text: k })])))));

  /* about */
  body.appendChild(el("div", { class: "settings-group" }, [
    el("h3", { text: "About" }),
    el("div", { class: "settings-row" }, [
      el("span", { class: "grow", text: "GimmeTools v" + S.boot.version }),
      el("button", { class: "btn btn-sm", text: "Check updates", onclick: manualUpdateCheck }),
    ]),
    el("div", { class: "settings-row" }, [
      el("button", { class: "btn btn-ghost btn-sm", text: "Open logs folder", onclick: () =>
        api.call("open_path", S.boot.root + "\\logs") }),
      el("button", { class: "btn btn-ghost btn-sm", text: "Open config folder", onclick: () =>
        api.call("open_path", S.boot.root + "\\config") }),
      el("button", { class: "btn btn-ghost btn-sm", text: "GitHub", onclick: () =>
        api.call("open_external", "https://github.com/imKaidenn/GimmeTools") }),
    ]),
  ]));

  async function save(values) {
    await api.call("save_settings", values);
    toast("Settings saved", "ok");
  }

  $("#settings-modal").classList.remove("hidden");
}

/* ── Updates ───────────────────────────────────────────────────────── */

window.onUpdateAvailable = (info) => {
  toast("GimmeTools " + info.latest + " is available", "", "Get it",
    () => api.call("open_external", info.url));
};

async function manualUpdateCheck() {
  toast("Checking for updates…");
  const info = await api.call("check_updates");
  if (info.available) window.onUpdateAvailable(info);
  else if (info.error) toast("Update check failed: " + info.error, "warn");
  else toast("You're on the latest version", "ok");
}

/* ── Queue actions ─────────────────────────────────────────────────── */

async function togglePause() {
  await api.call(S.queueState.paused ? "resume_queue" : "pause_queue");
  refreshState(true);
}

/* ── Global events ─────────────────────────────────────────────────── */

function wireEvents() {
  $("#palette-trigger").addEventListener("click", () => palette.show());
  $("#settings-btn").addEventListener("click", openSettings);
  $("#queue-pill").addEventListener("click", () => switchTab("queue"));
  $("#pause-btn").addEventListener("click", togglePause);
  $("#clear-history-btn").addEventListener("click", () =>
    confirmDialog("Clear history", "Remove all finished jobs from history?",
      async () => { await api.call("clear_history"); refreshState(true); }));
  $("#setup-run").addEventListener("click", async () => {
    await api.call("run_setup");
    $("#setup-banner").classList.add("hidden");
    toast("Setting up — this takes a few minutes the first time");
    switchTab("queue");
    refreshState(true);
  });

  document.querySelectorAll(".tab").forEach((t) =>
    t.addEventListener("click", () => switchTab(t.dataset.tab)));

  document.querySelectorAll("[data-close]").forEach((b) =>
    b.addEventListener("click", () => b.closest(".overlay").classList.add("hidden")));

  $("#palette-input").addEventListener("input", (e) => {
    palette.selected = 0;
    palette.render(e.target.value);
  });
  $("#palette-input").addEventListener("keydown", (e) => palette.key(e));
  $("#palette").addEventListener("mousedown", (e) => {
    if (e.target === $("#palette")) palette.hide();
  });
  $("#settings-modal").addEventListener("mousedown", (e) => {
    if (e.target === $("#settings-modal")) e.target.classList.add("hidden");
  });

  /* prevent the webview from navigating on stray drops */
  window.addEventListener("dragover", (e) => e.preventDefault());
  window.addEventListener("drop", (e) => e.preventDefault());

  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.key.toLowerCase() === "k") { e.preventDefault(); palette.open ? palette.hide() : palette.show(); return; }
    if (e.key === "Escape") {
      if (palette.open) { palette.hide(); return; }
      document.querySelectorAll(".overlay:not(.hidden)").forEach((o) => o.classList.add("hidden"));
      return;
    }
    if (palette.open) return;
    if (e.ctrlKey && e.key === "Enter") { e.preventDefault(); runCurrent(); }
    if (e.ctrlKey && e.key === ",") { e.preventDefault(); openSettings(); }
    if (e.ctrlKey && /^[1-9]$/.test(e.key)) {
      const i = parseInt(e.key, 10) - 1;
      if (S.tools[i]) { e.preventDefault(); selectTool(S.tools[i].id); }
    }
  });
}

/* ── Init ──────────────────────────────────────────────────────────── */

document.addEventListener("DOMContentLoaded", () => {
  wireEvents();
  boot().catch((err) => {
    document.body.appendChild(el("div", {
      style: "padding:24px;color:#fb7185;font-family:monospace;user-select:text",
      text: "GimmeTools UI failed to start: " + err,
    }));
  });
});
