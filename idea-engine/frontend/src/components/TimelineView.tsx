import React from "react";
import { ArrowDownLeft, ArrowUpRight, Clock } from "lucide-react";
import { TimelineEvent } from "../types/reports";
import { ChannelBadge } from "./ChannelBadge";

interface TimelineViewProps {
  events: TimelineEvent[];
}

export const TimelineView: React.FC<TimelineViewProps> = ({ events }) => {
  if (!events || events.length === 0) {
    return (
      <div style={{ padding: "24px", color: "var(--text-muted)", textAlign: "center" }}>
        No communication touchpoints recorded yet.
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px", position: "relative" }}>
      {events.map((event, index) => {
        const isInbound = event.direction === "INBOUND";
        const dateObj = new Date(event.timestamp);
        const timeFormatted = dateObj.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        const dateFormatted = dateObj.toLocaleDateString([], { month: "short", day: "numeric" });

        return (
          <div
            key={event.id || index}
            style={{
              display: "flex",
              gap: "14px",
              padding: "14px",
              backgroundColor: isInbound ? "rgba(198, 241, 53, 0.08)" : "var(--surface)",
              border: `1px solid ${isInbound ? "rgba(31, 90, 58, 0.2)" : "var(--border)"}`,
              borderRadius: "var(--radius-md)",
            }}
          >
            {/* Direction Icon & Time */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                minWidth: "65px",
                gap: "4px",
              }}
            >
              <div
                style={{
                  width: "28px",
                  height: "28px",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  backgroundColor: isInbound ? "var(--brand)" : "var(--surface-subtle)",
                  color: isInbound ? "var(--brand-foreground)" : "var(--text-secondary)",
                }}
              >
                {isInbound ? <ArrowDownLeft size={16} /> : <ArrowUpRight size={16} />}
              </div>
              <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--text-primary)" }}>
                {timeFormatted}
              </span>
              <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>
                {dateFormatted}
              </span>
            </div>

            {/* Event Body */}
            <div style={{ display: "flex", flexDirection: "column", gap: "6px", flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                <ChannelBadge channel={event.channel} />
                <span
                  style={{
                    fontSize: "11px",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    color: isInbound ? "var(--brand-deep)" : "var(--text-secondary)",
                  }}
                >
                  {event.direction}
                </span>

                {event.duration_seconds !== null && event.duration_seconds !== undefined && (
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "3px",
                      fontSize: "11px",
                      color: "var(--text-muted)",
                    }}
                  >
                    <Clock size={11} />
                    {event.duration_seconds}s
                  </span>
                )}

                {event.delivery_status && (
                  <span
                    style={{
                      fontSize: "11px",
                      color: "var(--text-muted)",
                      backgroundColor: "var(--surface-subtle)",
                      padding: "1px 6px",
                      borderRadius: "3px",
                    }}
                  >
                    {event.delivery_status}
                  </span>
                )}
              </div>

              {event.subject && (
                <div style={{ fontWeight: 600, fontSize: "13px", color: "var(--text-primary)" }}>
                  {event.subject}
                </div>
              )}

              <div
                style={{
                  fontSize: "13px",
                  color: "var(--text-primary)",
                  whiteSpace: "pre-wrap",
                  lineHeight: 1.45,
                }}
              >
                {event.content}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
