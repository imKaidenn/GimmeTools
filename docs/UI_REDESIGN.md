# GimmeTools — UI Redesign (v3 creator platform)

Two redesign generations live in this document. **v2** replaced the customtkinter
form with a web UI inside a native window. **v3** (current) rebuilds that into a
creator platform: Arc/Discord/CapCut/Linear/Spotify energy — cyberpunk but clean,
glassmorphism, neon gradients, a Creator Dashboard, and motion everywhere it earns
its keep.

## v3 design language

- **Typography**: Space Grotesk (display — headers, stats, brand) + Inter (UI), both
  bundled locally as variable woff2 (~69 KB total, no network, no FOUT beyond swap).
- **Surfaces**: deep-space base `#06050c` with a fixed ambient gradient mesh
  (purple/cyan/blue radials at low opacity); glass panels —
  `rgba(255,255,255,.03)` + `backdrop-filter: blur(16–28px)` + hairline strokes.
- **Color**: neon blue `#4d7cfe`, electric cyan `#22d3ee`, purple gradient
  `#7c3aed → #c084fc`; one brand gradient (purple→blue→cyan) for primary actions,
  gradient text, and progress. Soft glows (`box-shadow` color bloom) on active
  nav, primary buttons, icon tiles, and the busy status dot.
- **Motion** (all GPU-composited transform/opacity, 60fps): staggered sidebar
  entrance, animated view transitions (fade + 14px rise on a spring-ish
  `cubic-bezier(.16,1,.3,1)`), card hover lift + sheen sweep, icon tilt on hover,
  button press scale, chip pop-in, skeleton shimmer, toast slide. Entrance
  animations detach after settling (timer + `animationend`) so the compositor goes
  fully quiescent; `prefers-reduced-motion` collapses everything.
- **Personality**: empty states with voice ("Queue's clear. Drop something in and
  let the GPU eat."), time-aware greeting with the user's name in gradient text.

## v3 information architecture

```
┌──────────────┬───────────────────────────────────────────────┐
│ ⚡ GimmeTools │  HOME — Creator Dashboard                     │
│ 🔍 Search ⌘K │   kicker · "Good evening, <name>" · sub       │
│              │   [renders] [this week] [success %] [queued]  │
│ Home         │   Quick actions: gradient cards per tool      │
│ FAVORITES    │   Recent projects │ Activity timeline         │
│ IMAGE        │   Saved presets (chips → 1-click apply)       │
│ VIDEO        │                                               │
│ SYSTEM       │  TOOL — Workspace (glass card)                │
│ RECENT       │   ← back · gradient icon · ☆ · presets row    │
│              │   glowing drop zone → chips · options · ▶ Run │
│ ● status  ⚙ │  ───────────────────────────────────────────  │
│              │  Activity dock (floating glass)               │
└──────────────┴───────────────────────────────────────────────┘
```

The **Creator Dashboard** is the home view: greeting, live stats computed from job
history, quick-action cards (the four tools, category-gradient icon tiles, sheen on
hover), Recent projects (clickable rows with status badges), an Activity timeline
(gradient rail + status dots), and saved-preset chips that deep-link into a tool
with the preset applied. Skeleton shimmer placeholders render while the bridge
boots.

---

## v2 foundation (still accurate below)

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
