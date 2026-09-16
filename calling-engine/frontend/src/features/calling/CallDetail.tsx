import { useQuery } from "@tanstack/react-query";
import {
  Phone, ChevronLeft, Clock, Mic, FileText,
  Hash, ArrowUpDown, Wifi, AlertCircle,
} from "lucide-react";
import { Link } from "react-router-dom";
import { callingApi, callingKeys } from "../../api/calling";
import { CallBadge } from "./CallBadge";

function fmtDate(v: string | null): string {
  if (!v) return "—";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(v));
}

function fmtDuration(v: number | null): string {
  if (v == null) return "—";
  const m = Math.floor(v / 60);
  const s = String(v % 60).padStart(2, "0");
  return `${m}m ${s}s`;
}

export function CallDetail({ callId }: { callId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: callingKeys.detail(callId),
    queryFn:  () => callingApi.getCall(callId),
    retry: 1,
  });

  /* ── Loading ──────────────────────────────────────────────────────── */
  if (isLoading) {
    return (
      <div className="detail-loading">
        <div className="skeleton skeleton--title" />
        <div className="skeleton skeleton--body" style={{ width: "60%" }} />
        <div style={{ height: 12 }} />
        <div className="skeleton skeleton--body" />
        <div className="skeleton skeleton--body" />
        <div className="skeleton skeleton--body" style={{ width: "80%" }} />
      </div>
    );
  }

  /* ── Error ────────────────────────────────────────────────────────── */
  if (isError || !data?.data) {
    return (
      <div className="detail-error">
        <AlertCircle size={28} style={{ color: "var(--tx-lo)" }} />
        <p>Call record not found or you do not have access.</p>
        <Link to="/calling" className="btn-secondary">← Back to calls</Link>
      </div>
    );
  }

  const call = data.data;
  const isLive = ["QUEUED", "RINGING", "IN_PROGRESS"].includes(call.status);

  return (
    <>
      {/* ── Back ────────────────────────────────────────────────────── */}
      <Link to="/calling" className="back-btn">
        <ChevronLeft size={15} />
        All Calls
      </Link>

      <div className="detail-layout">
        {/* ── Main column ─────────────────────────────────────────── */}
        <div>
          {/* Hero card */}
          <div className="detail-hero">
            <div className="detail-hero-top">
              <div className="detail-hero-id">
                <div className="detail-hero-icon">
                  <Phone size={20} />
                </div>
                <div>
                  <div className="detail-hero-name">{call.lead_id}</div>
                  <div className="detail-hero-sub">
                    <span>{call.to_number ?? call.from_number ?? "Unknown number"}</span>
                    <span className="detail-hero-sep">·</span>
                    <span>{call.direction === "OUTBOUND" ? "Outbound" : "Inbound"}</span>
                    <span className="detail-hero-sep">·</span>
                    <span>{call.provider.toUpperCase()}</span>
                  </div>
                </div>
              </div>
              <CallBadge value={call.status} />
            </div>

            {/* Status strip */}
            <div className="detail-status-strip">
              <div className="detail-stat">
                <span className="detail-stat-label">Outcome</span>
                <span className="detail-stat-value"><CallBadge value={call.outcome} /></span>
              </div>
              <div className="detail-stat">
                <span className="detail-stat-label">Duration</span>
                <span className="detail-stat-value">
                  <Clock size={13} style={{ color: "var(--tx-lo)" }} />
                  {fmtDuration(call.duration_seconds)}
                </span>
              </div>
              <div className="detail-stat">
                <span className="detail-stat-label">Started</span>
                <span className="detail-stat-value">{fmtDate(call.started_at)}</span>
              </div>
              <div className="detail-stat">
                <span className="detail-stat-label">Ended</span>
                <span className="detail-stat-value">{fmtDate(call.ended_at)}</span>
              </div>
              <div className="detail-stat">
                <span className="detail-stat-label">Direction</span>
                <span className="detail-stat-value">
                  <ArrowUpDown size={13} style={{ color: "var(--tx-lo)" }} />
                  {call.direction === "OUTBOUND" ? "Outbound" : "Inbound"}
                </span>
              </div>
            </div>
          </div>

          {/* Summary */}
          {call.summary && (
            <div className="detail-section">
              <div className="detail-section-head">
                <FileText size={14} />
                AI Summary
              </div>
              <div className="detail-section-body">
                <p className="summary-text">{call.summary}</p>
              </div>
            </div>
          )}

          {/* Recording */}
          {call.recording_url && (
            <div className="detail-section">
              <div className="detail-section-head">
                <Mic size={14} />
                Recording
              </div>
              <div className="detail-section-body">
                <audio controls src={call.recording_url} className="audio-player" />
              </div>
            </div>
          )}

          {/* Transcript */}
          <div className="detail-section">
            <div className="detail-section-head">
              <FileText size={14} />
              Transcript
              {isLive && (
                <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--tx-lo)" }}>
                  Call in progress…
                </span>
              )}
            </div>
            <div className="detail-section-body">
              {call.transcript ? (
                <div className="transcript-wrap">
                  <pre className="transcript-text">{call.transcript}</pre>
                </div>
              ) : (
                <p className="transcript-empty">
                  {isLive
                    ? "Transcript will appear after the call completes."
                    : "No transcript available for this call."}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* ── Sidebar column ──────────────────────────────────────── */}
        <div>
          {/* Call info */}
          <div className="detail-sidebar-card">
            <div className="detail-sidebar-head">
              <Hash size={13} />
              Call Information
            </div>
            <div className="detail-sidebar-body">
              <div className="meta-list">
                <div className="meta-row">
                  <span className="meta-label">From</span>
                  <span className="meta-value">{call.from_number ?? "—"}</span>
                </div>
                <div className="meta-row">
                  <span className="meta-label">To</span>
                  <span className="meta-value">{call.to_number ?? "—"}</span>
                </div>
                <div className="meta-row">
                  <span className="meta-label">Provider</span>
                  <span className="meta-value">
                    <Wifi size={13} style={{ color: "var(--tx-lo)" }} />
                    {call.provider.toUpperCase()}
                  </span>
                </div>
                <div className="meta-row">
                  <span className="meta-label">Status</span>
                  <span className="meta-value"><CallBadge value={call.status} /></span>
                </div>
              </div>
            </div>
          </div>

          {/* IDs */}
          <div className="detail-sidebar-card">
            <div className="detail-sidebar-head">
              <Hash size={13} />
              Identifiers
            </div>
            <div className="detail-sidebar-body">
              <div className="meta-list">
                <div className="meta-row">
                  <span className="meta-label">Call ID</span>
                  <span className="meta-value"><code>{call.call_id}</code></span>
                </div>
                {call.conversation_id && (
                  <div className="meta-row">
                    <span className="meta-label">Conversation ID</span>
                    <span className="meta-value"><code>{call.conversation_id}</code></span>
                  </div>
                )}
                <div className="meta-row">
                  <span className="meta-label">Lead ID</span>
                  <span className="meta-value"><code>{call.lead_id}</code></span>
                </div>
                <div className="meta-row">
                  <span className="meta-label">Provider Call ID</span>
                  <span className="meta-value">
                    <code>{call.provider_call_id ?? "—"}</code>
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Timeline */}
          <div className="detail-sidebar-card">
            <div className="detail-sidebar-head">
              <Clock size={13} />
              Timeline
            </div>
            <div className="detail-sidebar-body">
              <div className="meta-list">
                <div className="meta-row">
                  <span className="meta-label">Started</span>
                  <span className="meta-value" style={{ fontSize: 12.5 }}>{fmtDate(call.started_at)}</span>
                </div>
                <div className="meta-row">
                  <span className="meta-label">Ended</span>
                  <span className="meta-value" style={{ fontSize: 12.5 }}>{fmtDate(call.ended_at)}</span>
                </div>
                <div className="meta-row">
                  <span className="meta-label">Duration</span>
                  <span className="meta-value">{fmtDuration(call.duration_seconds)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
