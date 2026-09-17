import { Bot, Cpu, User } from "lucide-react";
import { MessageResponse } from "../../api/agent";
import { SourceList } from "./SourceList";

interface MessageListProps {
  messages: MessageResponse[];
  isLoading?: boolean;
}

export function MessageList({ messages, isLoading }: MessageListProps) {
  if (messages.length === 0 && !isLoading) {
    return (
      <div className="agent-empty-chat">
        <Bot size={40} className="agent-empty-icon" />
        <h3>How can I assist you with T Rex?</h3>
        <p>
          Ask questions about T Rex modules, platform workflows, usage guidelines,
          or architecture. Answers are strictly grounded in the Agent Knowledge Base.
        </p>
      </div>
    );
  }

  return (
    <div className="agent-messages-scroll">
      {messages.map((msg) => {
        const isUser = msg.role === "user";
        const isFallback =
          !isUser &&
          msg.content.includes("I couldn't find enough information in the T Rex documentation");

        return (
          <div
            key={msg.id}
            className={`agent-message-row ${isUser ? "agent-message-user" : "agent-message-assistant"}`}
          >
            <div className="agent-avatar">
              {isUser ? <User size={18} /> : <Bot size={18} />}
            </div>
            <div className="agent-message-bubble">
              <div className="agent-message-header">
                <strong>{isUser ? "You" : "T Rex Assistant"}</strong>
                <span className="agent-message-time">
                  {new Date(msg.created_at).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
              <div className={`agent-message-content ${isFallback ? "agent-fallback-text" : ""}`}>
                {msg.content}
              </div>

              {!isUser && msg.sources && msg.sources.length > 0 && (
                <SourceList sources={msg.sources} />
              )}

              {!isUser && msg.generation && (
                <div className="agent-generation-info">
                  <Cpu size={12} />
                  <span>
                    {msg.generation.provider} / {msg.generation.model}
                  </span>
                </div>
              )}
            </div>
          </div>
        );
      })}

      {isLoading && (
        <div className="agent-message-row agent-message-assistant">
          <div className="agent-avatar">
            <Bot size={18} />
          </div>
          <div className="agent-message-bubble agent-loading-bubble">
            <span className="agent-typing-dot"></span>
            <span className="agent-typing-dot"></span>
            <span className="agent-typing-dot"></span>
          </div>
        </div>
      )}
    </div>
  );
}

