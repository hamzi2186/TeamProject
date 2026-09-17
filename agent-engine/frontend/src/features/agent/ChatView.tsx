import { AlertCircle, Bot, Sparkles } from "lucide-react";
import { ConversationDetail } from "../../api/agent";
import { MessageComposer } from "./MessageComposer";
import { MessageList } from "./MessageList";

interface ChatViewProps {
  conversation: ConversationDetail | null;
  isLoading: boolean;
  isSending: boolean;
  error: string | null;
  onSendMessage: (message: string) => void;
  onClearError: () => void;
}

export function ChatView({
  conversation,
  isLoading,
  isSending,
  error,
  onSendMessage,
  onClearError,
}: ChatViewProps) {
  return (
    <div className="agent-chat-main">
      <div className="agent-chat-header">
        <div className="agent-chat-header-title">
          <Bot size={20} className="agent-header-icon" />
          <h2>{conversation?.title || "Agent Assistant"}</h2>
          <span className="agent-tag">
            <Sparkles size={12} />
            <span>Grounded Multi-Turn RAG</span>
          </span>
        </div>
      </div>

      {error && (
        <div className="agent-error-banner">
          <AlertCircle size={16} />
          <span>{error}</span>
          <button type="button" className="agent-error-close" onClick={onClearError}>
            &times;
          </button>
        </div>
      )}

      <div className="agent-chat-body">
        {isLoading ? (
          <div className="agent-loading-state">
            <div className="agent-spinner"></div>
            <p>Loading conversation...</p>
          </div>
        ) : (
          <MessageList
            messages={conversation?.messages || []}
            isLoading={isSending}
          />
        )}
      </div>

      <div className="agent-chat-footer">
        <MessageComposer
          onSend={onSendMessage}
          isLoading={isSending}
          disabled={!conversation && !isLoading}
        />
      </div>
    </div>
  );
}

