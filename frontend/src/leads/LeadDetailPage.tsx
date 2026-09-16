import {
  AlertCircle,
  ArrowLeft,
  Database,
  ExternalLink,
  Globe2,
  Loader2,
  Mail,
  Phone,
  RefreshCw,
  Search,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Lead,
  LeadKnowledgeBaseStatus,
  LeadSearchResultItem,
  leadsApi,
} from "../api/leads";

function extractHostname(rawUrl: string): string {
  try {
    const formatted =
      rawUrl.startsWith("http://") || rawUrl.startsWith("https://")
        ? rawUrl
        : `https://${rawUrl}`;
    return new URL(formatted).hostname;
  } catch {
    return rawUrl;
  }
}

function getStatusBadgeClass(status: string) {
  const norm = status.toUpperCase();
  if (norm === "READY") return "ready";
  if (norm === "PARTIAL") return "warning";
  if (norm === "FAILED") return "danger";
  if (["QUEUED", "CRAWLING", "PROCESSING / EMBEDDING", "PROCESSING", "EMBEDDING", "REFRESHING"].includes(norm)) {
    return "info";
  }
  return "neutral";
}

export function LeadDetailPage() {
  const { leadId = "" } = useParams();
  const [lead, setLead] = useState<Lead | null>(null);
  const [error, setError] = useState("");
  const [kbStatus, setKbStatus] = useState<LeadKnowledgeBaseStatus | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [customWebsite, setCustomWebsite] = useState("");
  const [confirmDialog, setConfirmDialog] = useState<{ targetUrl: string } | null>(null);

  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<LeadSearchResultItem[] | null>(null);
  const [searchError, setSearchError] = useState("");

  const pollTimerRef = useRef<number | null>(null);

  const fetchKbStatus = async () => {
    try {
      const data = await leadsApi.getKnowledgeBase(leadId);
      setKbStatus(data);
      return data;
    } catch {
      return null;
    }
  };

  useEffect(() => {
    leadsApi
      .detail(leadId)
      .then((loadedLead) => {
        setLead(loadedLead);
        if (loadedLead.website_url) {
          setCustomWebsite(loadedLead.website_url);
        }
      })
      .catch((caught) =>
        setError(caught instanceof Error ? caught.message : "Could not load lead.")
      );

    fetchKbStatus();
  }, [leadId]);

  useEffect(() => {
    const statusUpper = kbStatus?.status?.toUpperCase() || "";
    const isWorking = [
      "QUEUED",
      "CRAWLING",
      "PROCESSING / EMBEDDING",
      "PROCESSING",
      "EMBEDDING",
      "REFRESHING",
    ].includes(statusUpper);

    if (isWorking) {
      pollTimerRef.current = setInterval(async () => {
        const latest = await fetchKbStatus();
        if (
          latest &&
          ![
            "QUEUED",
            "CRAWLING",
            "PROCESSING / EMBEDDING",
            "PROCESSING",
            "EMBEDDING",
            "REFRESHING",
          ].includes(latest.status.toUpperCase())
        ) {
          if (pollTimerRef.current) clearInterval(pollTimerRef.current);
          leadsApi.detail(leadId).then(setLead).catch(() => {});
        }
      }, 2500);
    } else {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    }

    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [kbStatus?.status, leadId]);

  const handleStartBuildClick = (urlToUse: string) => {
    if (!urlToUse.trim()) return;
    setConfirmDialog({ targetUrl: urlToUse.trim() });
  };

  const handleConfirmBuild = async () => {
    if (!confirmDialog) return;
    setActionLoading(true);
    setError("");
    try {
      const updated = await leadsApi.buildKnowledgeBase(leadId, confirmDialog.targetUrl);
      setKbStatus(updated);
      setConfirmDialog(null);
      const refreshedLead = await leadsApi.detail(leadId);
      setLead(refreshedLead);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Failed to build knowledge base."
      );
    } finally {
      setActionLoading(false);
    }
  };

  const handleRefresh = async () => {
    setActionLoading(true);
    setError("");
    try {
      const updated = await leadsApi.refreshKnowledgeBase(leadId);
      setKbStatus(updated);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Failed to refresh knowledge base."
      );
    } finally {
      setActionLoading(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    setSearchError("");
    try {
      const resp = await leadsApi.searchKnowledgeBase(leadId, searchQuery.trim(), 6);
      setSearchResults(resp.results);
    } catch (caught) {
      setSearchError(caught instanceof Error ? caught.message : "Search failed.");
      setSearchResults(null);
    } finally {
      setIsSearching(false);
    }
  };

  if (error && !lead) {
    return (
      <section className="page">
        <div className="notice error">{error}</div>
      </section>
    );
  }

  if (!lead) {
    return (
      <section className="page">
        <div className="loading-card">Loading lead…</div>
      </section>
    );
  }

  const activeWebsiteUrl = kbStatus?.website_url || lead.website_url;
  const currentKbStatus = (kbStatus?.status || "NOT_CREATED").toUpperCase();
  const isWorking = [
    "QUEUED",
    "CRAWLING",
    "PROCESSING / EMBEDDING",
    "PROCESSING",
    "EMBEDDING",
    "REFRESHING",
  ].includes(currentKbStatus);
  const isReadyOrPartial = currentKbStatus === "READY" || currentKbStatus === "PARTIAL";

  return (
    <section className="page">
      <Link className="back-link" to="/leads">
        <ArrowLeft size={16} />
        Back to leads
      </Link>

      {error && <div className="notice error" style={{ marginBottom: "18px" }}>{error}</div>}

      <div className="detail-hero">
        <div>
          <p className="eyebrow dark">Lead detail</p>
          <h1>{lead.display_name || "Unnamed lead"}</h1>
          <div className="contact-line">
            <span>
              <Mail size={16} />
              {lead.email || "No email"}
            </span>
            <span>
              <Phone size={16} />
              {lead.phone || "No phone"}
            </span>
            <span>
              <Globe2 size={16} />
              {activeWebsiteUrl || "No website"}
            </span>
          </div>
        </div>
        <span className="pill ready">{lead.current_status}</span>
      </div>

      <div className="detail-grid">
        <div className="detail-card">
          <h2>Overview</h2>
          <dl>
            <dt>HubSpot source ID</dt>
            <dd>{lead.hubspot_contact_id}</dd>
            <dt>Knowledge base</dt>
            <dd>
              {isReadyOrPartial
                ? `Ready (${kbStatus?.page_count ?? 0} pages)`
                : isWorking
                ? currentKbStatus
                : lead.website_id
                ? "Linked"
                : "Unavailable until website ingestion"}
            </dd>
            <dt>Last updated</dt>
            <dd>{new Date(lead.updated_at).toLocaleString()}</dd>
          </dl>
        </div>

        <div className="detail-card">
          <h2>Channel readiness</h2>
          <p>
            {lead.phone
              ? "Calling and SMS ready"
              : "Calling and SMS unavailable: missing phone"}
          </p>
          <p>
            {lead.email
              ? "Email ready"
              : "Email unavailable: missing address"}
          </p>
          <p>
            {isReadyOrPartial
              ? `Client KB ready (${kbStatus?.chunk_count ?? 0} chunks)`
              : activeWebsiteUrl
              ? "Website supplied"
              : "Client KB unavailable: missing website"}
          </p>
        </div>
      </div>

      {/* Client Knowledge Base Section */}
      <div className="detail-card kb-card">
        <div className="kb-card-header">
          <div className="kb-title-box">
            <Database size={20} />
            <h2>Knowledge Base</h2>
          </div>
          <span className={`pill ${getStatusBadgeClass(currentKbStatus)}`}>
            {currentKbStatus.replaceAll("_", " ")}
          </span>
        </div>

        {!activeWebsiteUrl ? (
          <div className="kb-no-website">
            <p className="kb-prompt-text">No website available for this lead.</p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleStartBuildClick(customWebsite);
              }}
              className="kb-url-form"
            >
              <input
                type="text"
                placeholder="https://example.com"
                value={customWebsite}
                onChange={(e) => setCustomWebsite(e.target.value)}
                required
              />
              <button
                type="submit"
                className="primary compact"
                disabled={actionLoading || !customWebsite.trim()}
              >
                Save &amp; Build Knowledge Base
              </button>
            </form>
          </div>
        ) : currentKbStatus === "NOT_CREATED" ? (
          <div className="kb-not-created-box">
            <dl className="kb-info-dl">
              <dt>Website:</dt>
              <dd>
                <a
                  href={
                    activeWebsiteUrl.startsWith("http")
                      ? activeWebsiteUrl
                      : `https://${activeWebsiteUrl}`
                  }
                  target="_blank"
                  rel="noopener noreferrer"
                  className="kb-link"
                >
                  {activeWebsiteUrl} <ExternalLink size={13} />
                </a>
              </dd>
              <dt>Knowledge Base:</dt>
              <dd>Not created</dd>
            </dl>
            <button
              type="button"
              className="primary"
              onClick={() => handleStartBuildClick(activeWebsiteUrl)}
              disabled={actionLoading}
            >
              Build Knowledge Base
            </button>
          </div>
        ) : isWorking ? (
          <div className="kb-building-box">
            <Loader2 className="spinner" size={24} />
            <div>
              <h3>{currentKbStatus}</h3>
              <p>
                Building client knowledge base from {activeWebsiteUrl}… This will take a few moments.
              </p>
            </div>
          </div>
        ) : isReadyOrPartial ? (
          <div className="kb-ready-box">
            <dl className="kb-info-dl">
              <dt>Website:</dt>
              <dd>
                <a
                  href={
                    activeWebsiteUrl.startsWith("http")
                      ? activeWebsiteUrl
                      : `https://${activeWebsiteUrl}`
                  }
                  target="_blank"
                  rel="noopener noreferrer"
                  className="kb-link"
                >
                  {activeWebsiteUrl} <ExternalLink size={13} />
                </a>
              </dd>
              <dt>Status:</dt>
              <dd>
                <span className={`pill ${getStatusBadgeClass(currentKbStatus)}`}>
                  {currentKbStatus}
                </span>
              </dd>
              <dt>Pages indexed:</dt>
              <dd>{kbStatus?.page_count ?? 0}</dd>
              <dt>Chunks generated:</dt>
              <dd>{kbStatus?.chunk_count ?? 0}</dd>
              <dt>Last indexed:</dt>
              <dd>
                {kbStatus?.last_indexed_at
                  ? new Date(kbStatus.last_indexed_at).toLocaleString()
                  : "Recently"}
              </dd>
            </dl>

            <div className="kb-action-row">
              <button
                type="button"
                className="secondary compact"
                onClick={handleRefresh}
                disabled={actionLoading}
              >
                <RefreshCw size={14} className={actionLoading ? "spinner" : ""} />
                Re-crawl Website
              </button>
            </div>

            {/* Knowledge Base Semantic Search */}
            <div className="kb-search-section">
              <h3>Search Knowledge Base</h3>
              <p className="kb-search-intro">
                Query this lead&apos;s indexed knowledge base to retrieve specific business information and sources.
              </p>
              <form onSubmit={handleSearch} className="kb-search-form">
                <div className="search-input-wrapper">
                  <Search size={16} className="search-icon" />
                  <input
                    type="text"
                    placeholder="Ask a question about this lead's business (e.g. What services do they offer?)"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                <button
                  type="submit"
                  className="primary compact"
                  disabled={isSearching || !searchQuery.trim()}
                >
                  {isSearching ? "Searching..." : "Search"}
                </button>
              </form>

              {searchError && <div className="notice error">{searchError}</div>}

              {searchResults && (
                <div className="kb-results-list">
                  {searchResults.length === 0 ? (
                    <p className="kb-empty-results">
                      No matching knowledge found for this query.
                    </p>
                  ) : (
                    searchResults.map((res) => (
                      <div key={res.chunk_id} className="kb-result-card">
                        <div className="kb-result-header">
                          <span className="kb-result-title">
                            {res.page_title || "Web Page"}
                          </span>
                          <span className="kb-similarity-score">
                            {Math.round(res.similarity * 100)}% match
                          </span>
                        </div>
                        <p className="kb-result-content">{res.content}</p>
                        <a
                          href={res.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="kb-result-link"
                        >
                          {res.source_url} <ExternalLink size={12} />
                        </a>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="notice error kb-failed-box">
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <AlertCircle size={18} />
              <strong>Knowledge base ingestion failed</strong>
            </div>
            <p style={{ margin: "8px 0" }}>
              {kbStatus?.error_message || "An unexpected error occurred during website processing."}
            </p>
            <button
              type="button"
              className="secondary compact"
              onClick={() => handleStartBuildClick(activeWebsiteUrl)}
              disabled={actionLoading}
            >
              Retry Build
            </button>
          </div>
        )}
      </div>

      {/* Confirmation Modal */}
      {confirmDialog && (
        <div className="modal-overlay" role="dialog" aria-modal="true">
          <div className="modal-card">
            <h3>Build Knowledge Base</h3>
            <p className="modal-body-text">
              Crawl <strong>{extractHostname(confirmDialog.targetUrl)}</strong> and build a
              knowledge base from its public website?
            </p>
            <div className="modal-footer">
              <button
                type="button"
                className="secondary"
                onClick={() => setConfirmDialog(null)}
                disabled={actionLoading}
              >
                Cancel
              </button>
              <button
                type="button"
                className="primary"
                onClick={handleConfirmBuild}
                disabled={actionLoading}
              >
                {actionLoading ? "Starting Crawl…" : "Confirm & Crawl"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
