import { ArrowUpRight, ChevronRight, Phone, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import type { Call } from "../../types/calling";
import { CallBadge } from "./CallBadge";

function fmtDate(v: string | null): string {
  if (!v) return "—";
  return new Intl.DateTimeFormat(undefined, {
    month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit",
  }).format(new Date(v));
}

function fmtDuration(v: number | null): string {
  if (v == null) return "—";
  const m = Math.floor(v / 60);
  const s = String(v % 60).padStart(2, "0");
  return `${m}m ${s}s`;
}

interface Props {
  calls: Call[];
  isRefetching?: boolean;
}

export function CallTable({ calls, isRefetching }: Props) {
  if (!calls.length) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">
          <Phone size={22} />
        </div>
        <h3>No calls yet</h3>
        <p>Completed conversations will appear here once campaigns start running.</p>
      </div>
    );
  }

  return (
    <div>
      {isRefetching && (
        <div className="table-refresh-bar">
          <RefreshCw size={12} className="spin" />
          Refreshing call data…
        </div>
      )}
      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Lead</th>
              <th>Direction</th>
              <th>Status</th>
              <th>Outcome</th>
              <th style={{ textAlign: "right" }}>Duration</th>
              <th style={{ textAlign: "right" }}>Started</th>
              <th style={{ width: 40 }} />
            </tr>
          </thead>
          <tbody>
            {calls.map((call) => (
              <tr
                key={call.call_id}
                onClick={() => { window.location.href = `/calling/${call.call_id}`; }}
              >
                <td>
                  <div className="cell-lead">
                    <Link
                      className="cell-lead-id"
                      to={`/calling/${call.call_id}`}
                      onClick={(e) => e.stopPropagation()}
                    >
                      {call.lead_id}
                      <ArrowUpRight size={12} style={{ color: "var(--tx-lo)" }} />
                    </Link>
                    <span className="cell-lead-num">
                      {call.to_number ?? call.from_number ?? "—"}
                    </span>
                  </div>
                </td>

                <td>
                  <span
                    className={`direction-pill direction-pill--${call.direction.toLowerCase()}`}
                  >
                    {call.direction === "OUTBOUND" ? "↑ Out" : "↓ In"}
                  </span>
                </td>

                <td><CallBadge value={call.status} /></td>
                <td><CallBadge value={call.outcome} /></td>

                <td className="cell-numeric">{fmtDuration(call.duration_seconds)}</td>
                <td className="cell-numeric">{fmtDate(call.started_at ?? call.ended_at)}</td>

                <td>
                  <Link
                    className="icon-btn"
                    aria-label="Open call detail"
                    to={`/calling/${call.call_id}`}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <ChevronRight size={16} />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
