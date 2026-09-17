import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock, Mic, Phone, FileText, ChevronLeft, Bot, User, Sparkles, PhoneOff } from "lucide-react";
import { Link } from "react-router-dom";
import { callingApi, callingKeys } from "../../api/calling";
import { CallBadge } from "./CallBadge";
import type { Call } from "../../types/calling";

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
  const queryClient = useQueryClient();
  const [endingCall, setEndingCall] = useState(false);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: callingKeys.detail(callId),
    queryFn: () => callingApi.getCall(callId),
    refetchInterval: (query) => {
      const callData = query.state.data?.data as Call | undefined;
      if (callData && ["COMPLETED", "FAILED", "NO_ANSWER", "CANCELLED"].includes(callData.status)) {
        return false;
      }
      return 1500;
    },
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
  const isLive = ["QUEUED", "RINGING", "IN_PROGRESS"].includes(call.status);

  // Parse lines into dialogue
  const dialogueLines = (call.transcript || "")
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .map((line, idx) => {
      const isAi = line.toLowerCase().startsWith("ai") || line.toLowerCase().startsWith("alex");
      const colonIdx = line.indexOf(":");
      const speaker = colonIdx !== -1 ? line.slice(0, colonIdx).trim() : (isAi ? "Alex (AI)" : "Lead");
      const text = colonIdx !== -1 ? line.slice(colonIdx + 1).trim() : line;
      return { id: idx, isAi, speaker, text };
    });

  const lastLine = dialogueLines.length > 0 ? dialogueLines[dialogueLines.length - 1] : null;
  const isAiSpeaking = isLive && (!lastLine || !lastLine.isAi);

  const handleEndCall = async () => {
    if (endingCall) return;
    setEndingCall(true);
    try {
      await callingApi.endCall(callId);
      await refetch();
      void queryClient.invalidateQueries({ queryKey: callingKeys.all });
    } catch (e) {
      console.error("Failed to end call", e);
    } finally {
      setEndingCall(false);
    }
  };

  return (
    <div className="call-detail">
      {/* Header */}
      <div className="call-detail__header">
        <Link to="/calling" className="back-link">
          <ChevronLeft size={16} />
          All Calls
        </Link>
        <div className="call-detail__title-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
            <div className="call-detail__icon">
              <Phone size={18} />
            </div>
            <div>
              <h1 className="call-detail__lead">Call Context: {call.lead_id}</h1>
              <p className="call-detail__sub">
                {call.to_number ?? call.from_number ?? "Unknown number"} ·{" "}
                {call.direction === "OUTBOUND" ? "Outbound" : "Inbound"} ·{" "}
                {call.provider.toUpperCase()}
              </p>
            </div>
          </div>

          {isLive && (
            <button
              type="button"
              className="hangup-button"
              onClick={handleEndCall}
              disabled={endingCall}
            >
              <PhoneOff size={16} />
              <span>{endingCall ? "Ending…" : "Hang Up"}</span>
            </button>
          )}
        </div>
      </div>

      {/* Live Audio & Speaking Visualizer */}
      {isLive && (
        <div className="live-visualizer-bar" style={{ borderRadius: "12px", margin: "0 0 20px" }}>
          <div className="live-speaker-status">
            <div className="speaking-row">
              <div className="soundwave">
                <span className="bar bar-1" />
                <span className="bar bar-2" />
                <span className="bar bar-3" />
                <span className="bar bar-4" />
                <span className="bar bar-5" />
              </div>
              <span className="speaker-text">
                {call.status === "RINGING"
                  ? "Ringing outbound contact line…"
                  : isAiSpeaking
                  ? "Alex (AI Voice Assistant) is speaking…"
                  : "Lead is responding…"}
              </span>
            </div>
          </div>
        </div>
      )}

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
            <h2>AI Qualification & Summary</h2>
          </div>
          <div className="call-detail__summary" style={{ background: "rgba(34, 197, 94, 0.08)", border: "1px solid rgba(74, 222, 128, 0.25)", padding: "16px", borderRadius: "12px", color: "#f1f5f9" }}>
            {call.summary}
          </div>
        </section>
      )}

      {/* Recording */}
      {call.recording_url && (
        <section className="call-detail__section">
          <div className="section-header">
            <Mic size={15} />
            <h2>Audio Recording</h2>
          </div>
          <audio controls src={call.recording_url} className="call-detail__audio" />
        </section>
      )}

      {/* Conversation Dialogue Stream */}
      <section className="call-detail__section">
        <div className="section-header">
          <Clock size={15} />
          <h2>Conversation Stream {isLive && <span style={{ color: "#4ade80", fontSize: "12px", fontWeight: 700, marginLeft: "8px" }}>● LIVE STREAM</span>}</h2>
        </div>
        {dialogueLines.length > 0 ? (
          <div className="dialogue-list" style={{ marginTop: "12px" }}>
            {dialogueLines.map((msg) => (
              <div
                key={msg.id}
                className={`dialogue-bubble ${msg.isAi ? "dialogue-ai" : "dialogue-lead"}`}
              >
                <div className="bubble-header">
                  <div className="bubble-avatar">
                    {msg.isAi ? <Bot size={15} /> : <User size={15} />}
                  </div>
                  <span className="bubble-author">{msg.speaker}</span>
                </div>
                <div className="bubble-text">{msg.text}</div>
              </div>
            ))}
          </div>
        ) : (
          <p className="muted">
            {isLive
              ? "Call connected — streaming speech from voice channel…"
              : "No transcript available for this call."}
          </p>
        )}
      </section>

      {/* Technical IDs */}
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
