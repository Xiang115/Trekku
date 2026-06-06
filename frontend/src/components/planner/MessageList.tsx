import { useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble";
import PlanningIndicator from "./PlanningIndicator";
import type { ProgressEvent } from "../../api/client";
import type { ConversationTurn } from "../../api/types";

const STARTERS = [
  "Plan a 3-day budget trip to Kuala Lumpur for 2 people",
  "Weekend foodie getaway in Petaling Jaya under RM 1500",
  "Family day out in Putrajaya for 4, relaxed pace",
];

export default function MessageList({
  conversation,
  isSending,
  progress,
  onStarter,
}: {
  conversation: ConversationTurn[];
  isSending: boolean;
  progress: ProgressEvent | null;
  onStarter: (text: string) => void;
}) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation.length, isSending]);

  if (conversation.length === 0 && !isSending) {
    return (
      <div className="chat-thread">
        <p className="chat-empty">
          Tell Trekku what trip you want to plan. Try one of these to get started:
        </p>
        <div className="starter-chips">
          {STARTERS.map((s) => (
            <button key={s} type="button" className="starter-chip" onClick={() => onStarter(s)}>
              {s}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="chat-messages">
      {conversation.map((turn, i) => (
        <MessageBubble key={`${turn.timestamp}-${i}`} turn={turn} />
      ))}
      {isSending && <PlanningIndicator progress={progress} />}
      <div ref={endRef} />
    </div>
  );
}
