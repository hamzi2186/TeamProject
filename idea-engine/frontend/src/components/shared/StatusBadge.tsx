import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { LeadOutcome, ReportStatus } from "@/types/reports";

type BadgeStatus = LeadOutcome | ReportStatus | string;

interface StatusBadgeProps {
  status: BadgeStatus;
  className?: string;
}

const STATUS_VARIANT: Record<string, { variant: "success" | "warning" | "danger" | "info" | "brand" | "secondary"; tone: string }> = {
  INTERESTED: { variant: "success", tone: "Interested" },
  CONVERTED: { variant: "success", tone: "Converted" },
  COMPLETED: { variant: "success", tone: "Completed" },
  FOLLOW_UP_REQUIRED: { variant: "warning", tone: "Follow-up required" },
  PROCESSING: { variant: "warning", tone: "Processing" },
  PENDING: { variant: "warning", tone: "Pending" },
  CONTACTING: { variant: "warning", tone: "Contacting" },
  DO_NOT_CONTACT: { variant: "danger", tone: "Do not contact" },
  FAILED: { variant: "danger", tone: "Failed" },
  UNDELIVERED: { variant: "danger", tone: "Undelivered" },
  NOT_INTERESTED: { variant: "secondary", tone: "Not interested" },
  NO_ANSWER: { variant: "secondary", tone: "No answer" },
  NO_RESPONSE: { variant: "secondary", tone: "No response" },
};

function toTitleCase(value: string): string {
  return value
    .toLowerCase()
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const key = status.toUpperCase();
  const config = STATUS_VARIANT[key];
  const label = config?.tone ?? toTitleCase(status);

  return (
    <Badge
      variant={config?.variant ?? "outline"}
      className={cn("whitespace-nowrap normal-case", className)}
      aria-label={`Status: ${label}`}
    >
      <span
        aria-hidden
        className={cn("size-1.5 rounded-full", {
          "bg-success": config?.variant === "success",
          "bg-warning": config?.variant === "warning",
          "bg-danger": config?.variant === "danger",
          "bg-info": config?.variant === "info",
          "bg-brand": config?.variant === "brand",
          "bg-border-strong": !config || config.variant === "secondary",
        })}
      />
      {label}
    </Badge>
  );
}