import React from "react";
import { LeadOutcome, ReportStatus } from "../types/reports";

interface StatusBadgeProps {
  status: LeadOutcome | ReportStatus | string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const norm = (status || "").toUpperCase();

  let bg = "#F1EFE9";
  let color = "#4F524A";
  let border = "#DDDCD6";

  switch (norm) {
    case "INTERESTED":
    case "CONVERTED":
    case "COMPLETED":
      bg = "rgba(31, 106, 69, 0.12)";
      color = "#1F6A45";
      border = "rgba(31, 106, 69, 0.25)";
      break;
    case "FOLLOW_UP_REQUIRED":
    case "PROCESSING":
    case "PENDING":
    case "CONTACTING":
      bg = "rgba(201, 137, 36, 0.12)";
      color = "#C98924";
      border = "rgba(201, 137, 36, 0.25)";
      break;
    case "DO_NOT_CONTACT":
    case "FAILED":
      bg = "rgba(201, 58, 50, 0.12)";
      color = "#C93A32";
      border = "rgba(201, 58, 50, 0.25)";
      break;
    case "NOT_INTERESTED":
    case "NO_ANSWER":
    case "NO_RESPONSE":
      bg = "#F1EFE9";
      color = "#686A63";
      border = "#DDDCD6";
      break;
  }

  const formatText = (txt: string) => {
    return txt.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
  };

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: "3px 9px",
        borderRadius: "12px",
        fontSize: "12px",
        fontWeight: 500,
        backgroundColor: bg,
        color: color,
        border: `1px solid ${border}`,
        whiteSpace: "nowrap",
      }}
    >
      <span
        style={{
          width: "6px",
          height: "6px",
          borderRadius: "50%",
          backgroundColor: color,
        }}
      />
      {formatText(norm)}
    </span>
  );
};
