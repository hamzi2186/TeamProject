import { apiRequest } from "./client";

export type Website = {
  id: string;
  original_url: string;
  normalized_url: string;
  normalized_key: string;
  crawl_status: string;
  last_crawled_at: string | null;
  content_fingerprint: string | null;
  knowledge_base_id: string | null;
  kb_status: string | null;
  page_count: number;
  chunk_count: number;
  leads_using_kb: number;
  created_at: string;
  updated_at: string;
};

export type Job = {
  id: string;
  website_id: string;
  knowledge_base_id: string;
  status: string;
  pages_discovered: number;
  pages_crawled: number;
  pages_indexed: number;
  chunks_generated: number;
  error_message: string | null;
  partial_reason: string | null;
};

export type Page = {
  id: string;
  title: string | null;
  canonical_url: string;
  http_status: number;
  depth: number;
  fetched_at: string;
};

export type SearchResponse = {
  results: Array<{
    chunk_id: string;
    content: string;
    source_url: string;
    page_title: string | null;
    similarity: number;
  }>;
  embedding_provider: string;
  embedding_model: string;
  embedding_dimension: number;
};

export const knowledgeApi = {
  list: () => apiRequest<Website[]>("/api/v1/websites"),
  get: (id: string) => apiRequest<Website>(`/api/v1/websites/${id}`),
  pages: (id: string) => apiRequest<Page[]>(`/api/v1/websites/${id}/pages`),
  status: (id: string) =>
    apiRequest<{ website: Website; job: Job | null }>(`/api/v1/websites/${id}/status`),
  ingest: (url: string) =>
    apiRequest<{ website: Website; job_id: string | null; reused: boolean }>(
      "/api/v1/websites/ingest",
      { method: "POST", body: JSON.stringify({ url, lead_ids: [] }) },
    ),
  refresh: (id: string) =>
    apiRequest<{ job_id: string | null; reused: boolean }>(`/api/v1/websites/${id}/refresh`, {
      method: "POST",
    }),
  search: (kbId: string, query: string) =>
    apiRequest<SearchResponse>(`/api/v1/knowledge-bases/${kbId}/search`, {
      method: "POST",
      body: JSON.stringify({ query, top_k: 6 }),
    }),
};

