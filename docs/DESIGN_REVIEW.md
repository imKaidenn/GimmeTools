# GimmeTools — Brutal Design Review (pre-polish audit)

Scored against the bar of a funded creator product (Arc / Linear / Raycast / Discord /
CapCut / Spotify). Anything below 9 got redesigned in the polish pass — the fixes are
documented per screen and in [POLISH_PHASE.md](POLISH_PHASE.md).

> **On screenshots:** the browser-preview capture tool was non-functional during the
> polish session, so verification was done with structural and computed-style
> assertions against the live page. "After" screenshots were subsequently captured
> from the **real running app** (Win32 `PrintWindow` on the actual WebView2 window):
> see [`screenshots/gimmetools.png`](../screenshots/gimmetools.png) (dashboard),
> [`palette.png`](../screenshots/palette.png), [`tool.png`](../screenshots/tool.png),
> and [`onboarding.png`](../screenshots/onboarding.png).

---

## Scorecard

| Surface | Before | Verdict | After target |
|---|---|---|---|
| Sidebar | 7.5 | Good bones; stagger + glow already there. Stars invisible until hover is right; section labels fine. Passed with minor touches. | 9 |
| Dashboard | 7 | Greeting + stats + cards strong, but static numbers, no guidance layer, nothing "for you". Felt like a nicely skinned report. | 9 |
| Tool workspace | 7 | Functional; Run button didn't celebrate success; no feedback loop after queueing beyond a toast. | 9 |
| Queue dock | 6.5 | **Worst surface.** Action buttons always visible = noisy rows; no right-click; utilitarian. | 9 |
| Command palette | 7.5 | Ranked search fine, but flat list, no groups, no footer hints, presets not searchable, nothing suggested. Raycast it was not. | 9.5 |
| Settings | 7 | Clean but list-like. Acceptable after shared-component upgrades (glass modal, toggles, focus rings). | 8.5 |
| Modals / dialogs | 7.5 | Solid glass treatment; input dialog plain but fine. | 9 |
| Toasts (notifications) | 7 | Text + colored edge only — no iconography, low glance value. | 9 |
| Context menus | 0 | Didn't exist. Browser default right-click in a "premium desktop app" is an instant tell. | 9 |
| Onboarding / first-run | 0 | Didn't exist. First impression was a bare dashboard. | 9 |
| Shortcut discoverability | 3 | Buried in Settings. No overlay, no `Ctrl /`. | 9 |
| Empty states | 7 | Already had personality copy; needed the visual treatment to match. | 9 |
| Loading states | 8 | Skeleton shimmer on boot already shipped in v3. | 9 |

**Average before: 5.8 — dragged down by the three missing surfaces. Nothing below 9
remains unaddressed.**

---

## The brutal part — what still smelled "developer project"

1. **No first-run moment.** Funded products sell themselves in the first 10 seconds;
   GimmeTools opened cold onto a dashboard with zero context. → 3-slide onboarding
   with animated art panel, progress dots, and a "Let's go" finisher.
2. **The palette was a search box, not a command surface.** No suggestions when empty,
   no groups, no keyboard hint footer, presets unreachable. → Suggested-first grouped
   browsing, ranked flat search, presets as first-class commands, Raycast-style footer.
3. **Queue rows shouted.** Three always-visible buttons per row read "admin dashboard".
   → Actions fade in on hover; right-click context menu (move/cancel/log) carries the
   power-user path.
4. **Success was silent.** Queueing a job only fired a toast in the corner; the button
   you actually pressed did nothing. → Run button morphs to a green "✓ Queued" state
   with a pop, then restores.
5. **Numbers just sat there.** Stats are the dashboard's hero, and they rendered like a
   spreadsheet. → 480ms ease-out count-up (reduced-motion aware, timer-backstopped).
6. **No guidance layer.** Nothing recommended, nothing taught. → "For you" cards from
   real state (recent failure → log deep-link; no presets after N renders → save-preset
   nudge; empty history → first-render suggestion) + rotating creator tips.
7. **Toasts were anonymous.** → Gradient icon orbs per severity (check/x/bolt/sparkle).
8. **Right-click did nothing.** → Custom glass context menu, 120ms pop, danger styling,
   viewport-clamped.
9. **Edge clipping.** Scrollable panels hard-clipped content. → 12px gradient mask
   fades on nav, panels, palette results.
10. **Keyboard affordances invisible.** → `Ctrl /` overlay; palette footer hints;
    `:focus-visible` purple rings; gradient `::selection`.

## What already passed (left alone deliberately)

- The glass + neon design system, bundled Space Grotesk/Inter, ambient gradient mesh
  (shipped in v3 and the strongest part of the app's identity).
- View transitions, staggered sidebar, card sheen sweeps — purposeful, 60fps,
  compositor-only.
- Empty-state copywriting ("Queue's clear. Drop something in and let the GPU eat.").
- The thin-UI architecture: nothing in the polish pass touches the backend contract.
