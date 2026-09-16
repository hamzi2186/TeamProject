# Client Knowledge Base API

The Scraper Engine owns website crawling, extraction, deterministic chunking, embeddings, pgvector storage, and retrieval. Calling, SMS, and Mailer consume this API over HTTP. They must not import Scraper source, call Jina, or issue pgvector SQL.

## Ownership and isolation

Every Client KB belongs to one canonical `app_users.id`. The same public website may be indexed independently by two tenants. All database retrieval predicates include both `user_id` and `knowledge_base_id` before vector ordering.

Customer endpoints derive `user_id` from the root platform RS256 access token. Internal consumers authenticate with `X-Scraper-Service-Token` and provide the canonical tenant ID resolved by their own authenticated business context.

## Customer endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/websites/normalize` | Normalize and validate a public URL |
| `POST` | `/api/v1/websites/ingest` | Create or reuse a site KB and queue indexing |
| `GET` | `/api/v1/websites` | List the authenticated tenant's sites |
| `GET` | `/api/v1/websites/{website_id}` | Inspect one owned site |
| `GET` | `/api/v1/websites/{website_id}/status` | Inspect KB and active job progress |
| `GET` | `/api/v1/websites/{website_id}/pages` | List indexed sources |
| `POST` | `/api/v1/websites/{website_id}/refresh` | Queue a safe replacement index |
| `GET` | `/api/v1/scrape-jobs/{job_id}` | Inspect one owned job |
| `GET` | `/api/v1/knowledge-bases/{kb_id}` | Inspect KB configuration |
| `POST` | `/api/v1/knowledge-bases/{kb_id}/search` | Search one owned ready KB |

Customer authentication:

```http
Authorization: Bearer eyJ...fake
```

Ingest request:

```json
{
  "url": "https://www.example.test/",
  "lead_ids": ["11111111-1111-4111-8111-111111111111"]
}
```

Search request:

```json
{
  "query": "What services does the company provide?",
  "top_k": 6,
  "minimum_similarity": 0.2
}
```

Search response:

```json
{
  "knowledge_base_id": "22222222-2222-4222-8222-222222222222",
  "query": "What services does the company provide?",
  "results": [
    {
      "chunk_id": "33333333-3333-4333-8333-333333333333",
      "knowledge_base_id": "22222222-2222-4222-8222-222222222222",
      "content": "Example Company provides implementation and support services.",
      "source_url": "https://www.example.test/services",
      "page_title": "Services",
      "chunk_index": 0,
      "similarity": 0.81,
      "metadata": {
        "source_url": "https://www.example.test/services",
        "token_count": 184
      }
    }
  ],
  "embedding_provider": "jina",
  "embedding_model": "jina-embeddings-v3",
  "embedding_dimension": 1024
}
```

## Internal retrieval endpoint

```http
POST /api/v1/internal/client-kb/search
X-Scraper-Service-Token: fake-internal-token
Content-Type: application/json
```

```json
{
  "user_id": "11111111-1111-4111-8111-111111111111",
  "knowledge_base_id": "22222222-2222-4222-8222-222222222222",
  "query": "What support is available?",
  "top_k": 6
}
```

The service token authenticates the calling engine. It does not replace tenant authorization. The caller must send the tenant ID already resolved from its authenticated campaign, lead, or conversation. Arbitrary browser-supplied tenant IDs are never trusted.

## Errors

| Status | Meaning |
|---:|---|
| `400` | Unsafe target, including SSRF or redirect SSRF |
| `401` | Missing or invalid customer/service authentication |
| `404` | Resource does not exist for that tenant |
| `409` | KB is not ready or its vector configuration is incompatible |
| `422` | Request validation failed |
| `502` | Embedding request failed without a safe retry classification |
| `503` | Auth, TPI, or a retryable embedding dependency is unavailable |

Provider payloads, authorization headers, stack traces, and credentials are never returned.

## Retrieval behavior

Stored chunks use `retrieval.passage`. Queries use `retrieval.query`. A query explicitly requests the KB's persisted provider, model, and dimension through TPI. A mismatch fails closed. Results use cosine similarity, default to six chunks, and always include source URL and page title.

