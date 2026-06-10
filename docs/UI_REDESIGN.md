# GimmeTools v2 — UI Redesign

The v1 UI was a single-window customtkinter form (mode selector, file row, options,
log box). Functional, but a utility launcher. v2 is a ground-up rebuild in web tech
inside a native window, taking cues from Raycast (command palette, keyboard-first),
Linear (typography, density, restraint), and Obsidian/Arc (sidebar structure) — on the
existing GimmeTools brand palette (near-black `#0a0911`, purple `#7c3aed`, cyan
`#22d3ee`).

## Information architecture

```
┌────────────┬──────────────────────────────────────────┐
│ GimmeTools │  Tool header (icon · name · ☆ favorite)  │
│ 🔍 Search  │  Preset row (apply / save / delete)      │
│            │  Drop zone  → file chips                 │
│ FAVORITES  │  Options grid (from the tool registry)   │
│ IMAGE      │  ▶ Run (Ctrl ↵)                          │
│ VIDEO      ├──────────────────────────────────────────┤
│ SYSTEM     │  Activity: Queue | History | Log         │
│ RECENT     │  pause/resume · reorder · cancel         │
│ ● status ⚙ │                                          │
└────────────┴──────────────────────────────────────────┘
```

- **Sidebar**: favorites (star any tool, persisted), tools grouped by category,
  recents (auto-tracked). Bottom: live queue status pill + settings.
- **Command palette (Ctrl+K)**: fuzzy search over all tools *and* actions (pause
  queue, settings, presets import/export, update check, open output folder…). Arrow
  keys + Enter; prefix/word/substring/subsequence ranking.
- **Tool view**: rendered entirely from the tool registry — option selects/toggles
  with help text, and registry constraints enforced live (choosing a fixed-4× model
  locks the Scale control to 4).
- **Activity panel**: Queue tab (running job with progress bar — determinate when the
  CLI emits `[i/n]`, indeterminate otherwise — plus reorder ↑↓ and cancel), History
  tab (status, duration, relative time; click for the log), Log tab (live-following
  monospace output).

## Workflow features

| Feature | Behavior |
|---|---|
| Drag & drop | Drop files or a folder anywhere on the drop zone; folders queue as one batch job, multiple files queue as separate jobs (reorderable). Falls back to Browse with a toast if the webview can't expose paths. |
| Batch queue | One job at a time (the tools saturate the GPU alone); pause finishes the current item then holds; resume continues. |
| Presets | Save the current options under a name per tool; apply from the preset row; same-name saves overwrite; import/export as self-describing JSON files. |
| Job history | Last 200 jobs with status, duration, log tail — survives restarts. |
| First-run | If the venv is missing, a banner offers one-click setup, which runs as a visible queue job with streamed output. |

## Feedback & state

- **Toasts** (top-right): job done/failed (failed includes a "View log" action),
  preset saved, settings saved, update available ("Get it" deep-link), warnings.
- **Loading**: spinner on the running job row; indeterminate progress bars; the
  sidebar status dot pulses cyan while busy, amber when paused.
- **Dialogs**: confirm for destructive actions (cancel job, delete preset, clear
  history); text-input dialog for preset names; native crash dialog for shell
  failures.

## Design system

- **Type**: Segoe UI Variable (system, no webfont download), 13px base, 11.5px
  uppercase labels with letter-spacing, Cascadia/Consolas for logs.
- **Spacing**: 4px grid throughout; radii 6/8/12; one shadow level for overlays.
- **Color**: 3 text tiers, 5 surface tiers, brand purple for primary actions only,
  cyan reserved for "alive" signals (status dot, progress gradient, brand accent).
- **Motion**: 120ms ease on hovers, 140ms pop for overlays, no decorative animation.

## Keyboard shortcuts

| Keys | Action |
|---|---|
| Ctrl K | Command palette |
| Ctrl ↵ | Run current tool |
| Ctrl , | Settings |
| Ctrl 1–4 | Switch tools |
| Esc | Close palette/dialogs |

## Verification

Screenshot-verified in this build: sidebar with favorites/recents and active states;
command palette with ranked results and category badges; settings panel (output
folder, behavior toggles, presets, shortcuts, about). Browser-mode mock
(`app.js` falls back when `pywebview` is absent) keeps the UI previewable and
developable without the shell.
