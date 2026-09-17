import { useState } from "react";
import { Check, MessageSquare, Pencil, Plus, Trash2, X } from "lucide-react";
import { ConversationSummary } from "../../api/agent";

interface ConversationListProps {
  conversations: ConversationSummary[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onRename: (id: string, newTitle: string) => void;
  onDelete: (id: string) => void;
  isLoading?: boolean;
}

export function ConversationList({
  conversations,
  activeId,
  onSelect,
  onCreate,
  onRename,
  onDelete,
  isLoading,
}: ConversationListProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  function startRename(e: React.MouseEvent, conv: ConversationSummary) {
    e.stopPropagation();
    setEditingId(conv.id);
    setEditTitle(conv.title || "Untitled Conversation");
  }

  function commitRename(e: React.MouseEvent, id: string) {
    e.stopPropagation();
    const trimmed = editTitle.trim();
    if (trimmed) {
      onRename(id, trimmed);
    }
    setEditingId(null);
  }

  function cancelRename(e: React.MouseEvent) {
    e.stopPropagation();
    setEditingId(null);
  }

  function confirmDelete(e: React.MouseEvent, id: string) {
    e.stopPropagation();
    onDelete(id);
    setDeletingId(null);
  }

  return (
    <aside className="agent-sidebar">
      <div className="agent-sidebar-header">
        <h3>Conversations</h3>
        <button
          type="button"
          className="agent-new-chat-btn"
          onClick={onCreate}
          disabled={isLoading}
        >
          <Plus size={16} />
          <span>New Chat</span>
        </button>
      </div>

      <div className="agent-conversation-items">
        {conversations.length === 0 ? (
          <div className="agent-no-conversations">
            <p>No conversations yet. Start a new chat to begin.</p>
          </div>
        ) : (
          conversations.map((conv) => {
            const isActive = conv.id === activeId;
            const isEditing = conv.id === editingId;
            const isConfirmingDelete = conv.id === deletingId;

            return (
              <div
                key={conv.id}
                className={`agent-conversation-item ${isActive ? "active" : ""}`}
                onClick={() => !isEditing && onSelect(conv.id)}
              >
                <MessageSquare size={16} className="agent-item-icon" />

                {isEditing ? (
                  <div className="agent-rename-box" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="text"
                      className="agent-rename-input"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      autoFocus
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitRename(e as any, conv.id);
                        if (e.key === "Escape") cancelRename(e as any);
                      }}
                    />
                    <button
                      type="button"
                      className="agent-icon-action confirm"
                      onClick={(e) => commitRename(e, conv.id)}
                      title="Save"
                    >
                      <Check size={14} />
                    </button>
                    <button
                      type="button"
                      className="agent-icon-action"
                      onClick={cancelRename}
                      title="Cancel"
                    >
                      <X size={14} />
                    </button>
                  </div>
                ) : (
                  <>
                    <span className="agent-item-title" title={conv.title || "Untitled"}>
                      {conv.title || "New Conversation"}
                    </span>

                    {isConfirmingDelete ? (
                      <div className="agent-delete-confirm-box" onClick={(e) => e.stopPropagation()}>
                        <span className="delete-prompt">Delete?</span>
                        <button
                          type="button"
                          className="agent-icon-action danger"
                          onClick={(e) => confirmDelete(e, conv.id)}
                          title="Confirm Delete"
                        >
                          <Check size={13} />
                        </button>
                        <button
                          type="button"
                          className="agent-icon-action"
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeletingId(null);
                          }}
                          title="Cancel"
                        >
                          <X size={13} />
                        </button>
                      </div>
                    ) : (
                      <div className="agent-item-actions">
                        <button
                          type="button"
                          className="agent-icon-action"
                          onClick={(e) => startRename(e, conv)}
                          title="Rename"
                        >
                          <Pencil size={13} />
                        </button>
                        <button
                          type="button"
                          className="agent-icon-action danger"
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeletingId(conv.id);
                          }}
                          title="Delete"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}

