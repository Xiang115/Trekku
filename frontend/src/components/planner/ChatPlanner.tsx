import { useChat } from "../../state/ChatContext";
import ChatComposer from "./ChatComposer";
import MessageList from "./MessageList";
import ParamsChips from "./ParamsChips";

export default function ChatPlanner() {
  const { conversation, paramsCollected, status, progress, error, send, resetSession } =
    useChat();
  const isSending = status === "sending";
  const city = paramsCollected?.city;
  const days = paramsCollected?.days;

  return (
    <section className="planner-shell" id="planner">
      <div className="planner-visual">
        <img src="/assets/trekku-trip-visual.png" alt="Trekku trip preview" />
        <div className="route-card">
          <span>{paramsCollected?.origin_state ?? "Malaysia"}</span>
          <strong>{city ?? "Plan your next trip"}</strong>
          <small>{days ? `${days} day${days > 1 ? "s" : ""}` : "AI-built itinerary"}</small>
        </div>
      </div>

      <div className="planner-panel">
        <div className="section-heading compact">
          <div>
            <div className="panel-kicker">AI Trip Planner</div>
            <h1>Chat your way to a complete trip.</h1>
          </div>
          {conversation.length > 0 && (
            <button className="outline-button" type="button" onClick={resetSession}>
              New trip
            </button>
          )}
        </div>

        <MessageList
          conversation={conversation}
          isSending={isSending}
          progress={progress}
          onStarter={send}
        />

        {error && <div className="error-note">{error}</div>}

        <ChatComposer onSend={send} disabled={isSending} />

        <ParamsChips params={paramsCollected} />
      </div>
    </section>
  );
}
