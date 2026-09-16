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

export type LeadKnowledgeBaseStatus = {
  has_website: boolean;
  website_url: string | null;
  website_id: string | null;
  knowledge_base_id: string | null;
  status: string;
  page_count: number;
  chunk_count: number;
  last_indexed_at: string | null;
  error_message: string | null;
};

export type LeadSearchResultItem = {
  chunk_id: string;
  content: string;
  source_url: string;
  page_title: string | null;
  similarity: number;
};

export type LeadSearchResponse = {
  knowledge_base_id: string;
  query: string;
  results: LeadSearchResultItem[];
};

export const leadsApi = {
  list: () => apiRequest<Lead[]>("/api/v1/leads"),
  detail: (leadId: string) => apiRequest<Lead>(`/api/v1/leads/${leadId}`),
  getKnowledgeBase: (leadId: string) =>
    apiRequest<LeadKnowledgeBaseStatus>(`/api/v1/leads/${leadId}/knowledge-base`),
  buildKnowledgeBase: (leadId: string, websiteUrl?: string) =>
    apiRequest<LeadKnowledgeBaseStatus>(`/api/v1/leads/${leadId}/knowledge-base/build`, {
      method: "POST",
      body: JSON.stringify({ website_url: websiteUrl || undefined }),
    }),
  refreshKnowledgeBase: (leadId: string) =>
    apiRequest<LeadKnowledgeBaseStatus>(`/api/v1/leads/${leadId}/knowledge-base/refresh`, {
      method: "POST",
    }),
  searchKnowledgeBase: (leadId: string, query: string, topK: number = 6) =>
    apiRequest<LeadSearchResponse>(`/api/v1/leads/${leadId}/knowledge-base/search`, {
      method: "POST",
      body: JSON.stringify({ query, top_k: topK }),
    }),
};
