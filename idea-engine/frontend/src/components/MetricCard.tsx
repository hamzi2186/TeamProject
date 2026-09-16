import React from "react";

interface MetricCardProps {
  label: string;
  value: number | string;
  subtext?: string;
  accentColor?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  subtext,
  accentColor,
}) => {
  return (
    <div
      className="card"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "6px",
        flex: 1,
        minWidth: "150px",
        borderTop: accentColor ? `3px solid ${accentColor}` : undefined,
      }}
    >
      <span style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: 500 }}>
        {label}
      </span>
      <span
        style={{
          fontSize: "26px",
          fontWeight: 600,
          color: "var(--text-primary)",
          letterSpacing: "-0.02em",
          lineHeight: 1.1,
        }}
      >
        {value}
      </span>
      {subtext && (
        <span style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>
          {subtext}
        </span>
      )}
    </div>
  );
};
