import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ConversationTurn } from "../../api/types";

export default function MessageBubble({ turn }: { turn: ConversationTurn }) {
  return (
    <div className={`chat-bubble ${turn.role}`}>
      {turn.role === "assistant" ? (
        <div className="chat-markdown">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              a: ({ node, ...props }) => (
                <a {...props} target="_blank" rel="noreferrer" />
              ),
            }}
          >
            {turn.content}
          </ReactMarkdown>
        </div>
      ) : (
        turn.content
      )}
    </div>
  );
}
