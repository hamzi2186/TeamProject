import { ArrowUpRight, ChevronRight, Phone, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import type { Call } from "../../types/calling";
import { CallBadge } from "./CallBadge";

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatDuration(value: number | null): string {
  if (value == null) return "—";
  const m = Math.floor(value / 60);
  const s = String(value % 60).padStart(2, "0");
  return `${m}m ${s}s`;
}

interface CallTableProps {
  calls: Call[];
  isRefetching?: boolean;
}

export function CallTable({ calls, isRefetching }: CallTableProps) {
  if (!calls.length) {
    return (
      <div className="empty-state">
        <Phone size={28} className="empty-state__icon" />
        <strong>No calls yet</strong>
        <span>Completed conversations will appear here once campaigns start running.</span>
      </div>
    );
  }

  return (
    <div className="table-wrap">
      {isRefetching && (
        <div className="table-refreshing">
          <RefreshCw size={14} className="spin" /> Refreshing…
        </div>
      )}
      <table className="data-table">
        <thead>
          <tr>
            <th>Lead</th>
            <th>Direction</th>
            <th>Status</th>
            <th>Outcome</th>
            <th>Duration</th>
            <th>Started</th>
            <th aria-label="Actions" />
          </tr>
        </thead>
        <tbody>
          {calls.map((call) => (
            <tr key={call.call_id} className="data-table__row">
              <td>
                <div className="lead-cell">
                  <Link className="lead-link" to={`/calling/${call.call_id}`}>
                    {call.lead_id}
                    <ArrowUpRight size={13} />
                  </Link>
                  <small>{call.to_number ?? call.from_number ?? "—"}</small>
                </div>
              </td>
              <td>
                <span className={`direction-tag direction-tag--${call.direction.toLowerCase()}`}>
                  {call.direction === "OUTBOUND" ? "↑ Out" : "↓ In"}
                </span>
              </td>
              <td>
                <CallBadge value={call.status} />
              </td>
              <td>
                <CallBadge value={call.outcome} />
              </td>
              <td className="numeric">{formatDuration(call.duration_seconds)}</td>
              <td className="numeric">{formatDate(call.started_at ?? call.ended_at)}</td>
              <td>
                <Link
                  className="icon-btn"
                  aria-label="Open call detail"
                  to={`/calling/${call.call_id}`}
                >
                  <ChevronRight size={17} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}