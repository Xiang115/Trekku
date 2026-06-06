# Interactive Waiting Experience — Design

**Date:** 2026-06-05
**Status:** Approved
**Area:** `frontend` (React + Vite + TypeScript)

## Problem

While the user waits for the AI planner to respond, the chat shows a single static
bubble — a pulsing dot plus the text "Trekku is planning…" (`MessageList.tsx:48-53`).
The `/agent/chat` endpoint is a single non-streaming POST, so the wait can be several
seconds with no feedback, which feels boring and slow.

## Goal

Replace the static indicator with a lively, animated waiting experience that makes the
wait feel shorter and on-brand. This is **purely client-side** — no backend or API
change.

## Non-Goals (explicitly out of scope)

- Skeleton/placeholder preview of the itinerary card.
- Destination-aware (city-specific) travel tips. Tips are general only.
- Real streamed / SSE progress from the backend. The status steps are decorative, not
  driven by actual backend phases.

## Design

### New component: `PlanningIndicator.tsx`

Location: `frontend/src/components/planner/PlanningIndicator.tsx`

- Self-contained, takes no props. Renders the full waiting UI inside an assistant chat
  bubble.
- Replaces the inline `chat-typing` block currently in `MessageList.tsx` (rendered when
  `isSending` is true).
- Manages two `setInterval` timers internally; clears both on unmount.
- Layout — two rows inside the assistant bubble:
  - **Row 1:** an animated plane gliding along a dotted route, followed by the current
    **rotating status step** text.
  - **Row 2:** `💡` icon plus a **rotating travel tip**.

### New copy module: `planningCopy.ts`

Location: `frontend/src/lib/planningCopy.ts`

- `PLANNING_STEPS: string[]` — ordered phases:
  1. "Understanding your trip…"
  2. "Searching for flights…"
  3. "Comparing hotels…"
  4. "Mapping out your days…"
  5. "Adding the finishing touches…"
- `TRAVEL_TIPS: string[]` — ~8 general Malaysia / SEA travel tips
  (e.g. "Grab is the easiest way to get around most Malaysian cities.").

### Behavior

- **Status steps:** advance every ~2.2s through `PLANNING_STEPS`, then **hold on the last
  step** for the remainder of the wait. Holding (rather than looping) avoids an awkward
  repeat or a false "done" signal, since real wait time is unknown.
- **Travel tips:** rotate every ~4.5s with a gentle fade transition. Start from a random
  index so the first tip varies per request.
- **Plane-along-route:** a looping CSS keyframe animation (plane translates along a dotted
  line).

### Styling

Added to `frontend/src/styles/additions.css`, reusing existing design tokens
(`--teal`, `--soft`, `--line`, `--muted`, `--ink`). New `@keyframes` for the plane glide
and a fade used for text swaps. Follows the existing `trekku-spin` keyframe pattern.

### Accessibility

- `aria-live="polite"` on the status text so screen readers announce progress.
- Respect `prefers-reduced-motion`: disable the plane glide and text fades, falling back
  to the existing static pulse + text.

## Testing

The frontend has no test runner configured (no `test` script, no vitest). Verification:

- `npm run build` (runs `tsc --noEmit`) for type-safety.
- Manual check in `npm run dev`: trigger a chat send and observe the rotating steps, tip
  rotation, plane animation, and reduced-motion fallback.
