import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clock, Info, Phone, PhoneCall, PhoneForwarded, PhoneMissed } from "lucide-react";
import { callingApi, callingKeys } from "../../api/calling";
import type { ListCallsParams } from "../../api/calling";
import { CallTable } from "../../features/calling/CallTable";

const STATUS_OPTIONS: Array<{ label: string; value: string }> = [
  { label: "All Statuses", value: "" },
  { label: "Queued", value: "QUEUED" },
  { label: "Ringing", value: "RINGING" },
  { label: "In Progress", value: "IN_PROGRESS" },
  { label: "Completed", value: "COMPLETED" },
  { label: "No Answer", value: "NO_ANSWER" },
  { label: "Failed", value: "FAILED" },
  { label: "Cancelled", value: "CANCELLED" },
];

const OUTCOME_OPTIONS: Array<{ label: string; value: string }> = [
  { label: "All Outcomes", value: "" },
  { label: "Interested", value: "INTERESTED" },
  { label: "Not Interested", value: "NOT_INTERESTED" },
  { label: "Follow Up", value: "FOLLOW_UP_REQUIRED" },
  { label: "Converted", value: "CONVERTED" },
  { label: "No Answer", value: "NO_ANSWER" },
  { label: "Do Not Contact", value: "DO_NOT_CONTACT" },
  { label: "Completed", value: "COMPLETED" },
  { label: "Failed", value: "FAILED" },
];

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s < 10 ? "0" : ""}${s}s`;
}

export function CallingListPage() {
  const [status, setStatus] = useState<string>("");
  const [outcome, setOutcome] = useState<string>("");
  const [leadId, setLeadId] = useState<string>("");

  const params: ListCallsParams = {
    ...(status && { status }),
    ...(outcome && { outcome }),
    ...(leadId && { lead_id: leadId }),
  };

  const { data, isLoading, isError, isRefetching, refetch } = useQuery({
    queryKey: callingKeys.list(params),
    queryFn: () => callingApi.listCalls(params),
    refetchInterval: 15_000,
    staleTime: 10_000,
  });

  const calls = data?.data ?? [];

  // Metrics computation (Task §9)
  const totalCalls = calls.length;
  const answeredCalls = calls.filter(
    (c) =>
      c.status === "COMPLETED" ||
      c.status === "IN_PROGRESS" ||
      (c.duration_seconds !== null && c.duration_seconds > 0)
  ).length;
  const noAnswerCalls = calls.filter(
    (c) => c.status === "NO_ANSWER" || c.outcome === "NO_ANSWER"
  ).length;
  const totalDuration = calls.reduce((acc, c) => acc + (c.duration_seconds || 0), 0);
  const avgDuration = answeredCalls > 0 ? Math.round(totalDuration / answeredCalls) : 0;

  return (
    <div className="page">
      {/* KB Pending / Mock Status Notice (Task §6) */}
      <div className="notice info" style={{ marginBottom: "1.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <Info size={16} />
        <span>
          <strong>Knowledge Base:</strong> Mock KB search active (Crawler / Scraper integration pending). Calls are non-blocking.
        </span>
      </div>

      {/* Page Header */}
      <div className="page-header">
        <div className="page-header__left">
          <div className="page-icon">
            <Phone size={20} />
          </div>
          <div>
            <h1 className="page-title">Calling Engine</h1>
            <p className="page-sub">
              {isLoading ? "Loading calls…" : `${totalCalls} total call${totalCalls !== 1 ? "s" : ""} recorded`}
            </p>
          </div>
        </div>
      </div>

      {/* Metrics Row (Task §9) */}
      <div className="metrics-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem", marginBottom: "1.5rem" }}>
        <div className="metric-card" style={{ background: "#fff", border: "1px solid var(--border)", borderRadius: "8px", padding: "1rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: "0.25rem" }}>
            <PhoneCall size={16} />
            <span>Calls Made</span>
          </div>
          <div style={{ fontSize: "1.75rem", fontWeight: 700 }}>{totalCalls}</div>
        </div>

        <div className="metric-card" style={{ background: "#fff", border: "1px solid var(--border)", borderRadius: "8px", padding: "1rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: "0.25rem" }}>
            <CheckCircle2 size={16} color="#16a34a" />
            <span>Answered</span>
          </div>
          <div style={{ fontSize: "1.75rem", fontWeight: 700, color: "#16a34a" }}>{answeredCalls}</div>
        </div>

        <div className="metric-card" style={{ background: "#fff", border: "1px solid var(--border)", borderRadius: "8px", padding: "1rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: "0.25rem" }}>
            <PhoneMissed size={16} color="#dc2626" />
            <span>No Answer</span>
          </div>
          <div style={{ fontSize: "1.75rem", fontWeight: 700, color: "#dc2626" }}>{noAnswerCalls}</div>
        </div>

        <div className="metric-card" style={{ background: "#fff", border: "1px solid var(--border)", borderRadius: "8px", padding: "1rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: "0.25rem" }}>
            <Clock size={16} />
            <span>Avg Duration</span>
          </div>
          <div style={{ fontSize: "1.75rem", fontWeight: 700 }}>{formatDuration(avgDuration)}</div>
        </div>
      </div>

      {/* Filters */}
      <div className="filter-bar">
        <div className="filter-bar__group">
          <label htmlFor="filter-status" className="sr-only">Filter by status</label>
          <select
            id="filter-status"
            className="select"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div className="filter-bar__group">
          <label htmlFor="filter-outcome" className="sr-only">Filter by outcome</label>
          <select
            id="filter-outcome"
            className="select"
            value={outcome}
            onChange={(e) => setOutcome(e.target.value)}
          >
            {OUTCOME_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div className="filter-bar__group filter-bar__group--grow">
          <label htmlFor="filter-lead" className="sr-only">Search by Lead ID</label>
          <input
            id="filter-lead"
            className="input"
            type="search"
            placeholder="Search Lead ID…"
            value={leadId}
            onChange={(e) => setLeadId(e.target.value)}
          />
        </div>

        {(status || outcome || leadId) && (
          <button
            className="btn-ghost"
            onClick={() => {
              setStatus("");
              setOutcome("");
              setLeadId("");
            }}
          >
            Clear
          </button>
        )}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="loading-rows">
          {[1, 2, 3, 4, 5].map((n) => (
            <div key={n} className="skeleton skeleton--row" />
          ))}
        </div>
      ) : isError ? (
        <div className="error-state">
          <p>Failed to load calls.</p>
          <button className="btn-secondary" onClick={() => refetch()}>Retry</button>
        </div>
      ) : (
        <CallTable calls={calls} isRefetching={isRefetching} />
      )}
    </div>
  );
}
