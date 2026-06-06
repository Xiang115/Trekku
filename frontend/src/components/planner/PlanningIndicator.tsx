import { useEffect, useState } from "react";
import type { ProgressEvent } from "../../api/client";
import { FALLBACK_STEPS, TRAVEL_TIPS, stageLabel } from "../../lib/planningCopy";

const STEP_INTERVAL_MS = 2200;
const TIP_INTERVAL_MS = 4500;

/**
 * Waiting indicator shown while the planner is generating a reply.
 *
 * The status line reflects the agent's REAL progress: `progress` carries the
 * latest streamed event and `stageLabel` renders friendly, specific copy
 * ("Searching flights to Penang…"). Before the first event arrives (or if a proxy
 * buffers the stream) it falls back to a gentle timed rotation. The plane-on-route
 * animation and travel tips stay decorative; both degrade gracefully under
 * prefers-reduced-motion via CSS.
 */
export default function PlanningIndicator({
  progress,
}: {
  progress: ProgressEvent | null;
}) {
  const realLabel = stageLabel(progress);
  const [fallbackIndex, setFallbackIndex] = useState(0);
  // Start tips at a random offset so the first tip varies per request.
  const [tipIndex, setTipIndex] = useState(() =>
    Math.floor(Math.random() * TRAVEL_TIPS.length),
  );

  // Rotate fallback steps only until real progress arrives; then hold (real copy drives it).
  useEffect(() => {
    if (realLabel) return;
    const id = setInterval(() => {
      setFallbackIndex((prev) => {
        if (prev >= FALLBACK_STEPS.length - 1) return prev;
        return prev + 1;
      });
    }, STEP_INTERVAL_MS);
    return () => clearInterval(id);
  }, [realLabel]);

  // Cycle tips continuously.
  useEffect(() => {
    const id = setInterval(() => {
      setTipIndex((prev) => (prev + 1) % TRAVEL_TIPS.length);
    }, TIP_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  const label = realLabel ?? FALLBACK_STEPS[fallbackIndex];

  return (
    <div className="chat-bubble assistant planning-indicator">
      <div className="planning-status">
        <span className="planning-route" aria-hidden="true">
          <span className="planning-plane">✈️</span>
        </span>
        <span className="planning-step" key={label} aria-live="polite">
          {label}
        </span>
      </div>
      <div className="planning-tip">
        <span className="planning-tip-icon" aria-hidden="true">
          💡
        </span>
        <span className="planning-tip-text" key={tipIndex}>
          {TRAVEL_TIPS[tipIndex]}
        </span>
      </div>
    </div>
  );
}
