// Copy shown in the chat while the AI planner is working.
//
// The status line is now driven by REAL backend progress events (see chatStream in
// api/client.ts) — `stageLabel` turns a streamed event into friendly, specific text.
// FALLBACK_STEPS covers the brief window before the first event arrives (or if a proxy
// buffers the stream). TRAVEL_TIPS remain purely decorative.

import type { ProgressEvent } from "../api/client";

/** Friendly-but-specific status text for a real backend progress event. */
export function stageLabel(ev: ProgressEvent | null): string | null {
  if (!ev) return null;
  const where = ev.detail ? ` ${ev.detail}` : "";
  switch (ev.stage) {
    case "understanding":
      return "Reading your trip details…";
    case "thinking":
      return "Thinking through your plan…";
    case "searching_flights":
      return `Searching flights${where ? ` to${where}` : ""}…`;
    case "searching_hotels":
      return `Comparing hotels${where ? ` in${where}` : ""}…`;
    case "searching_attractions":
      return `Finding things to do${where ? ` in${where}` : ""}…`;
    case "finalizing":
      return "Putting your itinerary together…";
    case "learning":
      return "Noting your preferences…";
    default:
      return null; // unknown stage → fall back, never blank
  }
}

// Shown on a timer until the first real event lands.
export const FALLBACK_STEPS: string[] = [
  "Understanding your trip…",
  "Searching for flights…",
  "Comparing hotels…",
  "Mapping out your days…",
  "Adding the finishing touches…",
];

export const TRAVEL_TIPS: string[] = [
  "Grab is the easiest way to get around most Malaysian cities.",
  "Carry small cash — many hawker stalls and night markets are cash-only.",
  "The best street food usually appears after sunset at the pasar malam.",
  "Pack a light layer — shopping malls and buses crank the air-con.",
  "Tap water isn't drinkable in most areas; stick to bottled or boiled water.",
  "Tipping isn't expected, but rounding up is always appreciated.",
  "Touch 'n Go cards make trains, tolls, and convenience stores painless.",
  "Mornings are cooler and less crowded — ideal for outdoor sights.",
];
