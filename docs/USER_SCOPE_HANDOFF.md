# T Rex — User Scope Implementation Handoff

## 1. Status

Overall status:  
READY FOR HANDOFF

Verified commit:  
`655e5bb1f460f65d1c6a599b7aa52192a94efd65`

Branch:  
`main`

State:  
clean and synchronized with `origin/main`

## 2. Completed Scope

The completed and verified user/shared scope includes:

- `MASTER_FINAL_PRD.md` v8 reconciliation
- Root Auth password security upgrade
- HubSpot OAuth integration
- HubSpot per-user connection ownership
- HubSpot lead import
- Lead → Website linking
- automatic Scraper Client KB ingestion
- Client KB tenant isolation
- Scraper partial-status correctness
- Scraper broker-dispatch recovery
- Agent regression verification

## 3. Architecture Flow

The verified user workflow is:

```text
Authenticated User
→ Root Backend
→ TPI
→ HubSpot OAuth
→ user-owned HubSpot connection
→ HubSpot contact import
→ canonical Lead
→ Scraper website normalization
→ canonical Website
→ Lead.website_id
→ asynchronous Scraper ingest
→ Client KB
→ tenant-safe vector retrieval
```

The Agent flow remains separate:

```text
Agent
→ Agent KB
→ TPI Agent Jina/Groq
```

Agent KB and Client KB are separate data and retrieval systems. Agent uses its documentation knowledge base and does not query customer Client KB tables.

## 4. Auth Security

- New registration passwords use Argon2id.
- Password resets store Argon2id hashes.
- Existing legacy SHA-256 password hashes remain compatible.
- A successful legacy login transparently upgrades the stored password hash to Argon2id.
- OTP and opaque-token lookup hashing remains separate and deterministic where required.
- Refresh-token rotation, logout, revocation, and password-reset session revocation remain operational.

## 5. HubSpot OAuth

- Root derives the authenticated user identity from the signed JWT.
- Root forwards that user's `user_id` to TPI when starting the HubSpot flow.
- TPI OAuth state is cryptographically random, expiring, and one-time.
- Callback ownership derives from the `user_id` stored in the consumed OAuth state, not from callback request input.
- `HUBSPOT_REDIRECT_URI` remains environment-driven and is validated as an absolute HTTP/HTTPS callback URI.
- Docker-only browser callback hosts are rejected in local/development configuration.
- Successful and failed callbacks redirect safely to the frontend with non-sensitive, allow-listed result indicators.
- Provider access tokens, refresh tokens, authorization codes, encrypted token payloads, and service credentials are never exposed through callback URLs.
- HubSpot connection and token ownership is scoped by `user_id`.
- Copying or reassigning OAuth credentials or encrypted tokens across users is prohibited and is not part of the product flow.

## 6. Lead and Website Automation

- HubSpot lead deduplication uses `(user_id, hubspot_contact_id)`.
- Website reuse uses `(user_id, normalized_key)`.
- Root calls the Scraper normalization API over the documented HTTP contract.
- Root does not contain a second website normalization implementation.
- `Lead.website_id` is linked through tenant-safe ownership checks.
- Contacts without a website continue to import normally without triggering Scraper ingestion.
- Scraper ingestion is asynchronous; import waits only for job creation/dispatch, not crawling and embedding completion.
- Repeated imports reuse legitimate active jobs and existing `READY` or `PARTIAL` Client KBs rather than creating unnecessary crawl jobs.

## 7. Client KB Isolation

- Website, knowledge-base, page, scrape-job, lead, and knowledge-chunk access is tenant-scoped.
- Internal Client KB search requires the `X-Scraper-Service-Token` header.
- Internal search requires both `user_id` and `knowledge_base_id`.
- Cross-user Client KB retrieval is rejected before vector search executes.

## 8. Scraper Reliability Fixes

### PARTIAL state

Successful partial crawls persist and report `PARTIAL` rather than being incorrectly stored as `READY`. Successful complete crawls continue to persist `READY`.

### Dispatch failure

If Celery dispatch fails:

- the API returns a sanitized HTTP 503 response;
- the owned, undispatched `QUEUED` job transitions to `FAILED`;
- no fake task ID is stored;
- a later ingest can create and dispatch a fresh job; and
- legitimate active jobs continue to deduplicate normally.

## 9. Agent Verification

- Agent uses `agent_documents` and `agent_knowledge_chunks`.
- Agent does not query Client KB tables.
- Agent Jina credentials are isolated from Scraper Jina credentials.
- Deterministic no-context fallback behavior remains intact.
- The Agent frontend remains available under `/agent/*`.

## 10. Verification Results

```text
Root backend: 39 passed
TPI backend: 36 passed
Scraper backend: 41 passed
Agent backend: 32 passed

Total: 148 passed

Frontend production build: PASS
git diff --check: PASS
git status: clean / synchronized with origin/main
```

## 11. Database/Migration Impact

- No migration was required for the recent Auth, HubSpot, Lead→Website automation, or Scraper reliability fixes.
- The architecture continues to use the single shared Supabase/PostgreSQL database.
- Migrations remain centralized under `backend/alembic/versions/`.

## 12. Deferred Operational Risks

1. **Broker publication acknowledgement ambiguity:** A broker could theoretically accept a Celery task immediately before the client reports dispatch failure. Eliminating this fully would require a transactional outbox or equivalent architecture and was intentionally out of scope. This is not a current release blocker.

2. **External environment acceptance:** Unit/integration tests use fixtures and mocks. Live HubSpot OAuth, Redis, Celery, Jina, and shared Supabase configuration still require deployment/environment-level acceptance testing. This is not a current release blocker.

## 13. Final Handoff State

READY FOR HANDOFF

No remaining confirmed user/shared-scope code defects were found by the final integration audit.
