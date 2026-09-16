import React from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  Phone,
  Mail,
  Globe,
  Activity,
} from "lucide-react";

import { fetchLeadJourney } from "../api/reports";
import { StatusBadge } from "../components/StatusBadge";
import { ChannelBadge } from "../components/ChannelBadge";
import { TimelineView } from "../components/TimelineView";

export const LeadSummaryPage: React.FC = () => {
  const { leadId } = useParams<{ leadId: string }>();

  const { data: journey, isLoading, isError, error } = useQuery({
    queryKey: ["leadJourney", leadId],
    queryFn: () => fetchLeadJourney(leadId!),
    enabled: !!leadId,
  });

  if (isLoading) {
    return (
      <div style={{ padding: "60px", textAlign: "center", color: "var(--text-muted)" }}>
        Loading lead journey...
      </div>
    );
  }

  if (isError || !journey) {
    return (
      <div style={{ padding: "60px", textAlign: "center", color: "var(--danger)" }}>
        <p>Could not load lead journey: {(error as Error)?.message || "Not found"}</p>
        <Link to="/reports" className="btn-secondary" style={{ marginTop: "16px", display: "inline-flex" }}>
          Back to Reports
        </Link>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* Top Header */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        <Link to="/reports" className="btn-secondary" style={{ height: "36px", padding: "0 10px" }}>
          <ArrowLeft size={16} />
          Back
        </Link>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <h1 style={{ fontSize: "22px", fontWeight: 700 }}>{journey.lead_name}</h1>
            <StatusBadge status={journey.final_outcome} />
          </div>
          <p style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "2px" }}>
            Lead 360° Intelligence & Chronological Journey
          </p>
        </div>
      </div>

      {/* Two-Column Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "20px", alignItems: "start" }}>
        {/* Left Column: Lead Profile & Intelligence Summary */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          {/* Contact Card */}
          <div className="card" style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <span style={{ fontWeight: 600, fontSize: "14px", borderBottom: "1px solid var(--border)", paddingBottom: "8px" }}>
              Lead Contact Info
            </span>

            <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "13px" }}>
              {journey.email && (
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <Mail size={14} color="var(--text-muted)" />
                  <span>{journey.email}</span>
                </div>
              )}
              {journey.phone && (
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <Phone size={14} color="var(--text-muted)" />
                  <span>{journey.phone}</span>
                </div>
              )}
              {journey.website_url && (
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <Globe size={14} color="var(--text-muted)" />
                  <a href={journey.website_url} target="_blank" rel="noreferrer" style={{ color: "var(--info)" }}>
                    {journey.website_url}
                  </a>
                </div>
              )}
            </div>

            <div style={{ marginTop: "6px" }}>
              <span style={{ fontSize: "11.5px", color: "var(--text-muted)", display: "block", marginBottom: "4px" }}>
                Channels Engaged
              </span>
              <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                {journey.channels_used.map((c) => (
                  <ChannelBadge key={c} channel={c} />
                ))}
              </div>
            </div>
          </div>

          {/* Intelligence Synthesis Card */}
          <div className="card" style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <span style={{ fontWeight: 600, fontSize: "14px", borderBottom: "1px solid var(--border)", paddingBottom: "8px" }}>
              Intelligence Evaluation
            </span>

            <div>
              <span style={{ fontSize: "11.5px", color: "var(--text-muted)", display: "block", fontWeight: 600 }}>
                Approach Timeline:
              </span>
              <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginTop: "2px", lineHeight: 1.45 }}>
                {journey.approach_summary}
              </p>
            </div>

            <div>
              <span style={{ fontSize: "11.5px", color: "var(--text-muted)", display: "block", fontWeight: 600 }}>
                Conversation Synthesis:
              </span>
              <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginTop: "2px", lineHeight: 1.45 }}>
                {journey.conversation_summary}
              </p>
            </div>

            <div>
              <span style={{ fontSize: "11.5px", color: "var(--text-muted)", display: "block", fontWeight: 600 }}>
                Outcome Evidence:
              </span>
              <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginTop: "2px", lineHeight: 1.45 }}>
                {journey.outcome_reason}
              </p>
            </div>

            {journey.recommended_next_action && (
              <div
                style={{
                  backgroundColor: "rgba(198, 241, 53, 0.15)",
                  border: "1px solid rgba(31, 90, 58, 0.2)",
                  padding: "10px",
                  borderRadius: "var(--radius-md)",
                  marginTop: "4px",
                }}
              >
                <span style={{ fontSize: "11.5px", fontWeight: 700, color: "var(--brand-deep)", display: "block" }}>
                  Recommended Action:
                </span>
                <p style={{ fontSize: "12.5px", color: "var(--text-primary)", marginTop: "2px" }}>
                  {journey.recommended_next_action}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Chronological Touchpoint Timeline */}
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border)", paddingBottom: "12px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <Activity size={16} color="var(--brand-deep)" />
              <span style={{ fontWeight: 600, fontSize: "15px" }}>Cross-Channel Journey Timeline</span>
            </div>
            <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
              {journey.timeline.length} touchpoint(s)
            </span>
          </div>

          <TimelineView events={journey.timeline} />
        </div>
      </div>
    </div>
  );
};
