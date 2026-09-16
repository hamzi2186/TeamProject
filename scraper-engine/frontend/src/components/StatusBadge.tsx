const stateClass: Record<string, string> = {
  READY: "success",
  COMPLETED: "success",
  PARTIAL: "warning",
  PENDING: "neutral",
  QUEUED: "neutral",
  CRAWLING: "info",
  PROCESSING: "info",
  EMBEDDING: "info",
  REFRESHING: "info",
  RUNNING: "info",
  FAILED: "danger",
};

export function StatusBadge({ status }: { status: string | null }) {
  const value = status ?? "Not started";
  return <span className={`status-badge ${stateClass[value] ?? "neutral"}`}>{value.replaceAll("_", " ")}</span>;
}

