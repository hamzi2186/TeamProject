import { apiRequest } from "./client";

export type Lead = {
  id: string;
  hubspot_contact_id: string;
  first_name: string | null;
  last_name: string | null;
  display_name: string | null;
  phone: string | null;
  email: string | null;
  website_url: string | null;
  website_id: string | null;
  current_status: string;
  created_at: string;
  updated_at: string;
};

export type ClientKbStage =
  | "NOT_STARTED"
  | "QUEUED"
  | "CRAWLING"
  | "EXTRACTING"
  | "EMBEDDING"
  | "READY"
  | "PARTIAL"
  | "FAILED";

export type ClientKbStatus = {
  has_website: boolean;
  website_url: string | null;
  website_id: string | null;
  knowledge_base_id: string | null;
  status: string;
  knowledge_base_status: string;
  processing_stage: ClientKbStage;
  pages_discovered: number;
  pages_processed: number;
  pages_succeeded: number;
  pages_failed: number | null;
  page_count: number;
  chunk_count: number;
  chunks_created: number;
  embeddings_created: number | null;
  started_at: string | null;
  updated_at: string | null;
  completed_at: string | null;
  last_indexed_at: string | null;
  error_message: string | null;
};

export const leadsApi = {
  list: () => apiRequest<Lead[]>("/api/v1/leads"),
  detail: (leadId: string) => apiRequest<Lead>(`/api/v1/leads/${leadId}`),
  knowledgeBaseStatus: (leadId: string) =>
    apiRequest<ClientKbStatus>(`/api/v1/leads/${leadId}/knowledge-base`),
  buildKnowledgeBase: (leadId: string, websiteUrl?: string | null) =>
    apiRequest<ClientKbStatus>(`/api/v1/leads/${leadId}/knowledge-base/build`, {
      method: "POST",
      body: JSON.stringify({ website_url: websiteUrl || null }),
    }),
  refreshKnowledgeBase: (leadId: string) =>
    apiRequest<ClientKbStatus>(`/api/v1/leads/${leadId}/knowledge-base/refresh`, {
      method: "POST",
    }),
};
