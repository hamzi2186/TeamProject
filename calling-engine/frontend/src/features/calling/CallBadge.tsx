import type { CallOutcome, CallStatus } from "../../types/calling";

type BadgeValue = CallStatus | CallOutcome | string | null | undefined;

const STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  QUEUED:            { label: "Queued",          cls: "badge badge--queued" },
  RINGING:           { label: "Ringing",         cls: "badge badge--ringing" },
  IN_PROGRESS:       { label: "In Progress",     cls: "badge badge--progress" },
  COMPLETED:         { label: "Completed",        cls: "badge badge--completed" },
  NO_ANSWER:         { label: "No Answer",        cls: "badge badge--no-answer" },
  FAILED:            { label: "Failed",           cls: "badge badge--failed" },
  CANCELLED:         { label: "Cancelled",        cls: "badge badge--cancelled" },
  // Outcomes
  INTERESTED:        { label: "Interested",       cls: "badge badge--interested" },
  NOT_INTERESTED:    { label: "Not Interested",   cls: "badge badge--not-interested" },
  FOLLOW_UP_REQUIRED:{ label: "Follow Up",        cls: "badge badge--follow-up" },
  CONVERTED:         { label: "Converted",        cls: "badge badge--converted" },
  DO_NOT_CONTACT:    { label: "Do Not Contact",   cls: "badge badge--dnc" },
};

export function CallBadge({ value }: { value: BadgeValue }) {
  if (!value) return <span className="badge badge--empty">—</span>;
  const cfg = STATUS_CONFIG[value] ?? { label: value, cls: "badge badge--default" };
  return <span className={cfg.cls}>{cfg.label}</span>;
}