import React from "react";
import { Phone, MessageSquare, Mail } from "lucide-react";
import { Channel } from "../types/reports";

interface ChannelBadgeProps {
  channel: Channel;
}

export const ChannelBadge: React.FC<ChannelBadgeProps> = ({ channel }) => {
  const norm = (channel || "").toUpperCase();

  let icon = <MessageSquare size={12} />;
  let label = "SMS";

  if (norm === "CALL") {
    icon = <Phone size={12} />;
    label = "CALL";
  } else if (norm === "EMAIL") {
    icon = <Mail size={12} />;
    label = "EMAIL";
  }

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "4px",
        padding: "2px 8px",
        borderRadius: "4px",
        fontSize: "11px",
        fontWeight: 600,
        backgroundColor: "var(--surface-subtle)",
        color: "var(--text-secondary)",
        border: "1px solid var(--border)",
        letterSpacing: "0.03em",
      }}
    >
      {icon}
      {label}
    </span>
  );
};
