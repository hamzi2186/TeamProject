import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Phone,
  CheckCircle2,
  PhoneMissed,
  Clock4,
  Info,
  Search,
  X,
} from "lucide-react";
import { callingApi, callingKeys } from "../../api/calling";
import type { ListCallsParams } from "../../api/calling";
import { CallTable } from "../../features/calling/CallTable";

const STATUS_OPTIONS = [
  { label: "All Statuses",  value: "" },
  { label: "Queued",        value: "QUEUED" },
  { label: "Ringing",       value: "RINGING" },
  { label: "In Progress",   value: "IN_PROGRESS" },
  { label: "Completed",     value: "COMPLETED" },
  { label: "No Answer",     value: "NO_ANSWER" },
  { label: "Failed",        value: "FAILED" },
  { label: "Cancelled",     value: "CANCELLED" },
];

const OUTCOME_OPTIONS = [
  { label: "All Outcomes",    value: "" },
  { label: "Interested",      value: "INTERESTED" },
  { label: "Not Interested",  value: "NOT_INTERESTED" },
  { label: "Follow Up",       value: "FOLLOW_UP_REQUIRED" },
  { label: "Converted",       value: "CONVERTED" },
  { label: "No Answer",       value: "NO_ANSWER" },
  { label: "Do Not Contact",  value: "DO_NOT_CONTACT" },
  { label: "Completed",       value: "COMPLETED" },
  { label: "Failed",          value: "FAILED" },
];

function fmtDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s < 10 ? "0" : ""}${s}s`;
}

interface MetricCardProps {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  color: "green" | "red" | "amber" | "blue" | "neutral";
  sub?: string;
}

function MetricCard({ label, value, icon, color, sub }: MetricCardProps) {
  return (
    <div className={`metric-card metric-card--${color}`}>
      <div className="metric-header">
        <span className="metric-label">{label}</span>
        <div className={`metric-icon-wrap metric-icon-wrap--${color}`}>
          {icon}
        </div>
      </div>
      <div className="metric-value">{value}</div>
      {sub && <div className="metric-footer">{sub}</div>}
    </div>
  );
}

export function CallingListPage() {
  const [status,  setStatus]  = useState("");
  const [outcome, setOutcome] = useState("");
  const [leadId,  setLeadId]  = useState("");

  const params: ListCallsParams = {
    ...(status  && { status }),
    ...(outcome && { outcome }),
    ...(leadId  && { lead_id: leadId }),
  };

  const { data, isLoading, isError, isRefetching, refetch } = useQuery({
    queryKey: callingKeys.list(params),
    queryFn:  () => callingApi.listCalls(params),
    refetchInterval: 15_000,
    staleTime:       10_000,
  });

  const calls = data?.data ?? [];

  /* ── Metrics ─────────────────────────────────────────────────────── */
  const total     = calls.length;
  const answered  = calls.filter(
    (c) => c.status === "COMPLETED" || c.status === "IN_PROGRESS" || (c.duration_seconds ?? 0) > 0
  ).length;
  const noAnswer  = calls.filter(
    (c) => c.status === "NO_ANSWER" || c.outcome === "NO_ANSWER"
  ).length;
  const converted = calls.filter((c) => c.outcome === "CONVERTED").length;
  const totalDur  = calls.reduce((a, c) => a + (c.duration_seconds ?? 0), 0);
  const avgDur    = answered > 0 ? Math.round(totalDur / answered) : 0;
  const answerRate = total > 0 ? Math.round((answered / total) * 100) : 0;

  const hasFilters = !!(status || outcome || leadId);

  return (
    <>
      {/* ── Page header ─────────────────────────────────────────────── */}
      <div className="page-header">
        <div className="page-header-left">
          <div className="page-icon-wrap">
            <Phone size={20} />
          </div>
          <div>
            <h1 className="page-title">Voice Calls</h1>
            <p className="page-subtitle">
              {isLoading
                ? "Loading call history…"
                : `${total} call${total !== 1 ? "s" : ""} recorded`}
            </p>
          </div>
        </div>
      </div>

      {/* ── KB notice ───────────────────────────────────────────────── */}
      <div className="notice notice--info">
        <Info size={14} />
        <span>
          <strong>Knowledge Base:</strong> Mock KB search active — Scraper integration pending. Calls proceed unblocked.
        </span>
      </div>

      {/* ── Metrics ─────────────────────────────────────────────────── */}
      <div className="metrics-row">
        <MetricCard
          label="Total Calls"
          value={total}
          icon={<Phone size={14} />}
          color="neutral"
          sub="all time"
        />
        <MetricCard
          label="Answered"
          value={answered}
          icon={<CheckCircle2 size={14} />}
          color="green"
          sub={`${answerRate}% answer rate`}
        />
        <MetricCard
          label="No Answer"
          value={noAnswer}
          icon={<PhoneMissed size={14} />}
          color="red"
          sub={total > 0 ? `${Math.round((noAnswer / total) * 100)}% of calls` : "—"}
        />
        <MetricCard
          label="Avg Duration"
          value={fmtDuration(avgDur)}
          icon={<Clock4 size={14} />}
          color="blue"
          sub={`${converted} converted`}
        />
      </div>

      {/* ── Table card ──────────────────────────────────────────────── */}
      <div className="section-card">
        {/* Header */}
        <div className="section-header">
          <div className="section-title">
            <Phone size={15} />
            Recent Calls
          </div>
          <span className="section-count">{total} records</span>
        </div>

        {/* Filters */}
        <div className="filter-bar">
          <div className="filter-group">
            <label htmlFor="fs" className="sr-only">Status</label>
            <select
              id="fs"
              className="select-filter"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <label htmlFor="fo" className="sr-only">Outcome</label>
            <select
              id="fo"
              className="select-filter"
              value={outcome}
              onChange={(e) => setOutcome(e.target.value)}
            >
              {OUTCOME_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          <div className="filter-group filter-group--grow">
            <label htmlFor="fl" className="sr-only">Search Lead ID</label>
            <div className="filter-input-wrap" style={{ width: "100%" }}>
              <span className="filter-input-icon"><Search size={13} /></span>
              <input
                id="fl"
                className="input-search"
                type="search"
                placeholder="Search by Lead ID…"
                value={leadId}
                onChange={(e) => setLeadId(e.target.value)}
              />
            </div>
          </div>

          {hasFilters && (
            <button
              className="btn-clear"
              onClick={() => { setStatus(""); setOutcome(""); setLeadId(""); }}
            >
              <X size={12} /> Clear
            </button>
          )}
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="loading-rows">
            {[1,2,3,4,5,6].map((n) => (
              <div key={n} className="skeleton skeleton--row" style={{ borderBottom: "1px solid var(--ws-border)" }} />
            ))}
          </div>
        ) : isError ? (
          <div className="error-state">
            <div className="error-state-icon">
              <PhoneMissed size={20} />
            </div>
            <p>Failed to load call records.</p>
            <button className="btn-secondary" onClick={() => refetch()}>Retry</button>
          </div>
        ) : (
          <CallTable calls={calls} isRefetching={isRefetching} />
        )}
      </div>
    </>
  );
}
