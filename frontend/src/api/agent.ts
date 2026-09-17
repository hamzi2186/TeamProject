import { getToken } from "../auth/auth";

const AGENT_API_BASE = import.meta.env.VITE_AGENT_API_BASE_URL ?? "http://localhost:8003";

export interface AssistantSourceItem {
  module_key: string;
  source_path: string;
  header_path?: string | null;
  similarity?: number;
}

export interface AssistantGenerationInfo {
  provider: string;
  model: string;
  input_tokens?: number | null;
  output_tokens?: number | null;
}

export interface MessageResponse {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  sources: AssistantSourceItem[];
  generation?: AssistantGenerationInfo | null;
  created_at: string;
}

export interface ConversationSummary {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  messages: MessageResponse[];
}

export interface ConversationAskResponse {
  conversation_id: string;
  user_message: MessageResponse;
  assistant_message: MessageResponse;
}

export async function agentFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const response = await fetch(`${AGENT_API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message = body.detail?.message || body.detail || body.message || "Request failed";
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }

  return response.status === 204 ? (undefined as T) : (response.json() as Promise<T>);
}

export const agentApi = {
  createConversation: (title?: string) =>
    agentFetch<ConversationSummary>("/api/v1/agent/conversations", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),

  listConversations: () =>
    agentFetch<ConversationSummary[]>("/api/v1/agent/conversations"),

  getConversation: (conversationId: string) =>
    agentFetch<ConversationDetail>(`/api/v1/agent/conversations/${conversationId}`),

  renameConversation: (conversationId: string, title: string) =>
    agentFetch<ConversationSummary>(`/api/v1/agent/conversations/${conversationId}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),

  deleteConversation: (conversationId: string) =>
    agentFetch<void>(`/api/v1/agent/conversations/${conversationId}`, {
      method: "DELETE",
    }),

  postMessage: (conversationId: string, content: string) =>
    agentFetch<ConversationAskResponse>(`/api/v1/agent/conversations/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
};

