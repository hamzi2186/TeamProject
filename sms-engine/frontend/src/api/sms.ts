import type { BulkCampaignCreate, BulkCampaignResult, Conversation, ConversationCreate, ConversationDetail } from "../types/sms";

const API_BASE = import.meta.env.VITE_SMS_API_BASE_URL ?? "http://localhost:8002";
const DEMO_USER_ID = import.meta.env.VITE_DEMO_USER_ID ?? "";

function headers(): HeadersInit {
  const token = sessionStorage.getItem("trex_access_token");
  if (token) return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  return { "X-Demo-User-Id": DEMO_USER_ID, "Content-Type": "application/json" };
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...headers(), ...init.headers },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail ?? "The SMS service could not complete the request.");
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const smsApi = {
  list: () => request<Conversation[]>("/api/v1/sms/conversations"),
  detail: (id: string) => request<ConversationDetail>(`/api/v1/sms/conversations/${id}`),
  create: (payload: ConversationCreate) =>
    request<Conversation>("/api/v1/sms/conversations", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  bulkLaunch: (payload: BulkCampaignCreate) =>
    request<BulkCampaignResult>("/api/v1/sms/conversations/bulk", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  start: (id: string) =>
    request<{ accepted: boolean }>(`/api/v1/sms/conversations/${id}/start`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  mockReply: (id: string, body: string) =>
    request<{ accepted: boolean }>(`/api/v1/sms/conversations/${id}/mock-reply`, {
      method: "POST",
      body: JSON.stringify({ body }),
    }),
};

export function conversationSocketUrl(id: string): string {
  const url = new URL(API_BASE);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = `/ws/sms/conversations/${id}`;
  const token = sessionStorage.getItem("trex_access_token");
  if (token) url.searchParams.set("access_token", token);
  else url.searchParams.set("demo_user_id", DEMO_USER_ID);
  return url.toString();
}
