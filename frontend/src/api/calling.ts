import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { Call, CallsResponse, CallResponse } from "../types/calling";

export interface ListCallsParams {
  status?: string;
  outcome?: string;
  lead_id?: string;
}

export interface StartCallRequest {
  lead_id: string;
  phone_number: string;
  purpose?: string;
  campaign_id?: string;
  lead_variables?: Record<string, string>;
}

export const callingApi = {
  listCalls: (params: ListCallsParams = {}): Promise<CallsResponse> => {
    const qs = new URLSearchParams();
    if (params.status) qs.set("status", params.status);
    if (params.outcome) qs.set("outcome", params.outcome);
    if (params.lead_id) qs.set("lead_id", params.lead_id);
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return apiFetch<CallsResponse>(`/api/v1/calling/calls${query}`);
  },

  getCall: (callId: string): Promise<CallResponse> =>
    apiFetch<CallResponse>(`/api/v1/calling/calls/${callId}`),

  startCall: (request: StartCallRequest) =>
    apiFetch<{ success: boolean; data: { call_id: string; provider_call_id: string | null; status: string }; error: string | null }>(
      "/api/v1/calling/calls",
      { method: "POST", body: JSON.stringify(request) },
    ),

  endCall: (callId: string) =>
    apiFetch<{ success: boolean; data: Call; error: string | null }>(
      `/api/v1/calling/calls/${callId}/end`,
      { method: "POST" },
    ),

  searchKB: (callId: string, query: string): Promise<{ success: boolean; data: { results: unknown[] } }> =>
    apiFetch(`/api/v1/calling/tools/search-client-kb`, {
      method: "POST",
      body: JSON.stringify({ call_id: callId, query }),
    }),
};

// React Query key factories
export const callingKeys = {
  all: ["calls"] as const,
  list: (params: ListCallsParams) => [...callingKeys.all, "list", params] as const,
  detail: (callId: string) => [...callingKeys.all, "detail", callId] as const,
};

export function useCalls(params: ListCallsParams = {}) {
  return useQuery({
    queryKey: callingKeys.list(params),
    queryFn: async () => (await callingApi.listCalls(params)).data,
  });
}

export function useCall(callId: string | undefined) {
  return useQuery({
    enabled: Boolean(callId),
    queryKey: callingKeys.detail(callId ?? ""),
    queryFn: async () => (await callingApi.getCall(callId as string)).data,
  });
}