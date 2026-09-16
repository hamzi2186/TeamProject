import { useQuery } from "@tanstack/react-query";
import { Clock, Mic, Phone, FileText, ChevronLeft } from "lucide-react";
import { Link } from "react-router-dom";
import { callingApi, callingKeys } from "../../api/calling";
import { CallBadge } from "./CallBadge";

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatDuration(value: number | null): string {
  if (value == null) return "—";
  const m = Math.floor(value / 60);
  const s = String(value % 60).padStart(2, "0");
  return `${m}m ${s}s`;
}

export function CallDetail({ callId }: { callId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: callingKeys.detail(callId),
    queryFn: () => callingApi.getCall(callId),
    retry: 1,
  });

  if (isLoading) {
    return (
      <div className="detail-loading">
        <div className="skeleton skeleton--title" />
        <div className="skeleton skeleton--body" />
        <div className="skeleton skeleton--body" />
      </div>
    );
  }

  if (isError || !data?.data) {
    return (
      <div className="detail-error">
        <p>Call record not found or you do not have access.</p>
        <Link to="/calling" className="btn-secondary">← Back to calls</Link>
      </div>
    );
  }

  const call = data.data;

  return (
    <div className="call-detail">
      {/* Header */}
      <div className="call-detail__header">
        <Link to="/calling" className="back-link">
          <ChevronLeft size={16} />
          All Calls
        </Link>
        <div className="call-detail__title-row">
          <div className="call-detail__icon">
            <Phone size={18} />
          </div>
          <div>
            <h1 className="call-detail__lead">{call.lead_id}</h1>
            <p className="call-detail__sub">
              {call.to_number ?? call.from_number ?? "Unknown number"} ·{" "}
              {call.direction === "OUTBOUND" ? "Outbound" : "Inbound"} ·{" "}
              {call.provider.toUpperCase()}
            </p>
          </div>
        </div>
      </div>

      {/* Status row */}
      <div className="call-detail__status-bar">
        <div className="status-item">
          <span className="status-label">Status</span>
          <CallBadge value={call.status} />
        </div>
        <div className="status-item">
          <span className="status-label">Outcome</span>
          <CallBadge value={call.outcome} />
        </div>
        <div className="status-item">
          <span className="status-label">Duration</span>
          <span className="status-value">{formatDuration(call.duration_seconds)}</span>
        </div>
        <div className="status-item">
          <span className="status-label">Started</span>
          <span className="status-value">{formatDate(call.started_at)}</span>
        </div>
        <div className="status-item">
          <span className="status-label">Ended</span>
          <span className="status-value">{formatDate(call.ended_at)}</span>
        </div>
      </div>

      {/* Summary */}
      {call.summary && (
        <section className="call-detail__section">
          <div className="section-header">
            <FileText size={15} />
            <h2>Summary</h2>
          </div>
          <div className="call-detail__summary">{call.summary}</div>
        </section>
      )}

      {/* Recording */}
      {call.recording_url && (
        <section className="call-detail__section">
          <div className="section-header">
            <Mic size={15} />
            <h2>Recording</h2>
          </div>
          <audio controls src={call.recording_url} className="call-detail__audio" />
        </section>
      )}

      {/* Transcript */}
      <section className="call-detail__section">
        <div className="section-header">
          <Clock size={15} />
          <h2>Transcript</h2>
        </div>
        {call.transcript ? (
          <pre className="call-detail__transcript">{call.transcript}</pre>
        ) : (
          <p className="muted">
            {["QUEUED", "RINGING", "IN_PROGRESS"].includes(call.status)
              ? "Call is in progress — transcript will appear after completion."
              : "No transcript available for this call."}
          </p>
        )}
      </section>

      {/* IDs */}
      <section className="call-detail__section call-detail__ids">
        <dl>
          <dt>Call ID</dt>
          <dd><code>{call.call_id}</code></dd>
          <dt>Provider Call ID</dt>
          <dd><code>{call.provider_call_id ?? "—"}</code></dd>
          <dt>Lead ID</dt>
          <dd><code>{call.lead_id}</code></dd>
        </dl>
      </section>
    </div>
  );
}
