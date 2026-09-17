import { KeyboardEvent, useState } from "react";
import { Send } from "lucide-react";

interface MessageComposerProps {
  onSend: (message: string) => void;
  isLoading: boolean;
  disabled?: boolean;
}

export function MessageComposer({ onSend, isLoading, disabled }: MessageComposerProps) {
  const [text, setText] = useState("");

  function handleSubmit() {
    const trimmed = text.trim();
    if (!trimmed || isLoading || disabled) return;
    onSend(trimmed);
    setText("");
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  return (
    <div className="agent-composer-container">
      <textarea
        className="agent-composer-input"
        placeholder={disabled ? "Select or create a conversation to begin..." : "Ask a question about T Rex documentation (Press Enter to send)..."}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={isLoading || disabled}
        rows={2}
      />
      <button
        type="button"
        className="agent-send-button"
        onClick={handleSubmit}
        disabled={!text.trim() || isLoading || disabled}
        title="Send message"
      >
        <Send size={18} />
      </button>
    </div>
  );
}

