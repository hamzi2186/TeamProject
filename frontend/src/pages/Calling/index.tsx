import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Phone } from "lucide-react";
import { callingApi, callingKeys } from "../../api/calling";
import type { ListCallsParams } from "../../api/calling";
import { CallTable } from "../../features/calling/CallTable";
import type { CallStatus, CallOutcome } from "../../types/calling";

const STATUS_OPTIONS: Array<{ label: string; value: string }> = [
  { label: "All Statuses", value: "" },
  { label: "Queued", value: "QUEUED" },
  { label: "Ringing", value: "RINGING" },
  { label: "In Progress", value: "IN_PROGRESS" },
  { label: "Completed", value: "COMPLETED" },
  { label: "No Answer", value: "NO_ANSWER" },
  { label: "Failed", value: "FAILED" },
  { label: "Cancelled", value: "CANCELLED" },
];

const OUTCOME_OPTIONS: Array<{ label: string; value: string }> = [
  { label: "All Outcomes", value: "" },
  { label: "Interested", value: "INTERESTED" },
  { label: "Not Interested", value: "NOT_INTERESTED" },
  { label: "Follow Up", value: "FOLLOW_UP_REQUIRED" },
  { label: "Converted", value: "CONVERTED" },
  { label: "No Answer", value: "NO_ANSWER" },
  { label: "Do Not Contact", value: "DO_NOT_CONTACT" },
  { label: "Completed", value: "COMPLETED" },
  { label: "Failed", value: "FAILED" },
];

export function CallingListPage() {
  const [status, setStatus] = useState<string>("");
  const [outcome, setOutcome] = useState<string>("");
  const [leadId, setLeadId] = useState<string>("");

  const params: ListCallsParams = {
    ...(status && { status }),
    ...(outcome && { outcome }),
    ...(leadId && { lead_id: leadId }),
  };

  const { data, isLoading, isError, isRefetching, refetch } = useQuery({
    queryKey: callingKeys.list(params),
    queryFn: () => callingApi.listCalls(params),
    refetchInterval: 15_000, // Auto-refresh every 15s for live call status
    staleTime: 10_000,
  });

  const calls = data?.data ?? [];

  return (
    <div className="page">
      {/* Page header */}
      <div className="page-header">
        <div className="page-header__left">
          <div className="page-icon">
            <Phone size={18} />
          </div>
          <div>
            <h1 className="page-title">Calls</h1>
            <p className="page-sub">
              {isLoading ? "Loading…" : `${calls.length} call${calls.length !== 1 ? "s" : ""}`}
            </p>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="filter-bar">
        <div className="filter-bar__group">
          <label htmlFor="filter-status" className="sr-only">Filter by status</label>
          <select
            id="filter-status"
            className="select"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div className="filter-bar__group">
          <label htmlFor="filter-outcome" className="sr-only">Filter by outcome</label>
          <select
            id="filter-outcome"
            className="select"
            value={outcome}
            onChange={(e) => setOutcome(e.target.value)}
          >
            {OUTCOME_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div className="filter-bar__group filter-bar__group--grow">
          <label htmlFor="filter-lead" className="sr-only">Search by Lead ID</label>
          <input
            id="filter-lead"
            className="input"
            type="search"
            placeholder="Search Lead ID…"
            value={leadId}
            onChange={(e) => setLeadId(e.target.value)}
          />
        </div>

        {(status || outcome || leadId) && (
          <button
            className="btn-ghost"
            onClick={() => { setStatus(""); setOutcome(""); setLeadId(""); }}
          >
            Clear
          </button>
        )}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="loading-rows">
          {[1, 2, 3, 4, 5].map((n) => (
            <div key={n} className="skeleton skeleton--row" />
          ))}
        </div>
      ) : isError ? (
        <div className="error-state">
          <p>Failed to load calls.</p>
          <button className="btn-secondary" onClick={() => refetch()}>Retry</button>
        </div>
      ) : (
        <CallTable calls={calls} isRefetching={isRefetching} />
      )}
    </div>
  );
}
