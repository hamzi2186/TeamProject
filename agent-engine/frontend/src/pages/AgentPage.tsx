import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { agentApi } from "../api/agent";
import { ConversationList } from "../features/agent/ConversationList";
import { ChatView } from "../features/agent/ChatView";

export function AgentPage() {
  const { conversationId } = useParams<{ conversationId?: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // 1. Fetch conversations list
  const {
    data: conversations = [],
    isLoading: isLoadingConversations,
  } = useQuery({
    queryKey: ["agent-conversations"],
    queryFn: agentApi.listConversations,
  });

  // 2. Fetch active conversation details
  const {
    data: conversation,
    isLoading: isLoadingConversation,
    error: conversationError,
  } = useQuery({
    queryKey: ["agent-conversation", conversationId],
    queryFn: () => agentApi.getConversation(conversationId!),
    enabled: !!conversationId,
  });

  // Auto-select latest conversation if on root and list has items
  useEffect(() => {
    if (!conversationId && conversations.length > 0) {
      navigate(`/${conversations[0].id}`, { replace: true });
    }
  }, [conversationId, conversations, navigate]);

  // Sync conversation query error to error banner
  useEffect(() => {
    if (conversationError) {
      const msg = (conversationError as any).message || "Failed to load conversation";
      setErrorMessage(msg);
    }
  }, [conversationError]);

  // 3. Mutations
  const createMutation = useMutation({
    mutationFn: (title?: string) => agentApi.createConversation(title),
    onSuccess: (newConv) => {
      queryClient.invalidateQueries({ queryKey: ["agent-conversations"] });
      navigate(`/${newConv.id}`);
      setErrorMessage(null);
    },
    onError: (err: any) => {
      setErrorMessage(err.message || "Failed to create conversation");
    },
  });

  const renameMutation = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      agentApi.renameConversation(id, title),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent-conversations"] });
      if (conversationId) {
        queryClient.invalidateQueries({ queryKey: ["agent-conversation", conversationId] });
      }
    },
    onError: (err: any) => {
      setErrorMessage(err.message || "Failed to rename conversation");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => agentApi.deleteConversation(id),
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ["agent-conversations"] });
      if (conversationId === deletedId) {
        navigate("/");
      }
    },
    onError: (err: any) => {
      setErrorMessage(err.message || "Failed to delete conversation");
    },
  });

  const sendMessageMutation = useMutation({
    mutationFn: async (content: string) => {
      let targetId = conversationId;
      if (!targetId) {
        const created = await agentApi.createConversation();
        targetId = created.id;
        navigate(`/${targetId}`);
      }
      return agentApi.postMessage(targetId, content);
    },
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["agent-conversations"] });
      queryClient.invalidateQueries({ queryKey: ["agent-conversation", res.conversation_id] });
      setErrorMessage(null);
    },
    onError: (err: any) => {
      setErrorMessage(err.message || "Failed to send message to Agent assistant");
    },
  });

  return (
    <div className="agent-page-container">
      <ConversationList
        conversations={conversations}
        activeId={conversationId ?? null}
        onSelect={(id) => {
          setErrorMessage(null);
          navigate(`/${id}`);
        }}
        onCreate={() => createMutation.mutate(undefined)}
        onRename={(id, title) => renameMutation.mutate({ id, title })}
        onDelete={(id) => deleteMutation.mutate(id)}
        isLoading={isLoadingConversations || createMutation.isPending}
      />
      <ChatView
        conversation={conversation ?? null}
        isLoading={isLoadingConversation}
        isSending={sendMessageMutation.isPending}
        error={errorMessage}
        onSendMessage={(content) => sendMessageMutation.mutate(content)}
        onClearError={() => setErrorMessage(null)}
      />
    </div>
  );
}

