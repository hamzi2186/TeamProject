import React, { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  Download,
  Search,
  Filter,
  ChevronRight,
  Phone,
  Mail,
  Globe,
} from "lucide-react";

import { fetchReportDetail } from "../api/reports";
import { getDownloadUrl } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import { ChannelBadge } from "../components/ChannelBadge";
import { MetricCard } from "../components/MetricCard";

export const ReportDetailPage: React.FC = () => {
  const { reportId } = useParams<{ reportId: string }>();
  const [search, setSearch] = useState("");
  const [outcomeFilter, setOutcomeFilter] = useState("ALL");

  const { data: report, isLoading, isError, error } = useQuery({
    queryKey: ["reportDetail", reportId],
    queryFn: () => fetchReportDetail(reportId!),
    enabled: !!reportId,
  });

  if (isLoading) {
    return (
      <div style={{ padding: "60px", textAlign: "center", color: "var(--text-muted)" }}>
        Loading report details...
      </div>
    );
  }

  if (isError || !report) {
    return (
      <div style={{ padding: "60px", textAlign: "center", color: "var(--danger)" }}>
        <p>Could not load report: {(error as Error)?.message || "Not found"}</p>
        <Link to="/reports" className="btn-secondary" style={{ marginTop: "16px", display: "inline-flex" }}>
          Back to Reports
        </Link>
      </div>
    );
  }

  const items = report.items || [];
  const filteredItems = items.filter((item) => {
    const matchesSearch =
      item.lead_name.toLowerCase().includes(search.toLowerCase()) ||
      (item.company_website && item.company_website.toLowerCase().includes(search.toLowerCase())) ||
      (item.email && item.email.toLowerCase().includes(search.toLowerCase()));

    const matchesOutcome =
      outcomeFilter === "ALL" || item.final_outcome.toUpperCase() === outcomeFilter.toUpperCase();

    return matchesSearch && matchesOutcome;
  });

  const counts = report.summary_counts;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* Top Navigation & Actions */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <Link to="/reports" className="btn-secondary" style={{ height: "36px", padding: "0 10px" }}>
            <ArrowLeft size={16} />
            Reports
          </Link>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <h1 style={{ fontSize: "22px", fontWeight: 700 }}>
                Lead Intelligence Report — {report.report_date}
              </h1>
              <StatusBadge status={report.status} />
            </div>
            <p style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "2px" }}>
              Generated on {report.generated_at ? new Date(report.generated_at).toLocaleString() : "N/A"} • {report.total_leads} leads reviewed
            </p>
          </div>
        </div>

        <a
          href={getDownloadUrl(report.id)}
          download
          className="btn-primary"
          style={{ height: "40px", padding: "0 18px" }}
        >
          <Download size={16} />
          Download Full DOCX
        </a>
      </div>

      {/* KPI Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "12px" }}>
        <MetricCard label="Total Leads" value={counts.total_leads} />
        <MetricCard label="Interested" value={counts.interested} accentColor="var(--success)" />
        <MetricCard label="Converted" value={counts.converted} accentColor="var(--brand-deep)" />
        <MetricCard label="Follow-up" value={counts.follow_up_required} accentColor="var(--warning)" />
        <MetricCard label="Not Interested" value={counts.not_interested} />
        <MetricCard label="No Answer/Response" value={counts.no_answer + counts.no_response} />
        <MetricCard label="Do Not Contact" value={counts.do_not_contact} accentColor="var(--danger)" />
      </div>

      {/* Search and Filters Bar */}
      <div className="card" style={{ padding: "14px 18px", display: "flex", justifyContent: "space-between", alignItems: "center", gap: "16px", flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flex: 1, minWidth: "220px", position: "relative" }}>
          <Search size={16} color="var(--text-muted)" style={{ position: "absolute", left: "10px" }} />
          <input
            type="text"
            placeholder="Search lead by name, website, or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              width: "100%",
              height: "36px",
              paddingLeft: "34px",
              paddingRight: "12px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border)",
              fontSize: "13px",
              backgroundColor: "var(--surface)",
              color: "var(--text-primary)",
              outline: "none",
            }}
          />
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Filter size={15} color="var(--text-muted)" />
          <select
            value={outcomeFilter}
            onChange={(e) => setOutcomeFilter(e.target.value)}
            style={{
              height: "36px",
              padding: "0 12px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border)",
              backgroundColor: "var(--surface)",
              fontSize: "13px",
              color: "var(--text-primary)",
            }}
          >
            <option value="ALL">All Outcomes ({items.length})</option>
            <option value="INTERESTED">Interested ({counts.interested})</option>
            <option value="CONVERTED">Converted ({counts.converted})</option>
            <option value="FOLLOW_UP_REQUIRED">Follow-up Required ({counts.follow_up_required})</option>
            <option value="NOT_INTERESTED">Not Interested ({counts.not_interested})</option>
            <option value="NO_ANSWER">No Answer ({counts.no_answer})</option>
            <option value="NO_RESPONSE">No Response ({counts.no_response})</option>
            <option value="DO_NOT_CONTACT">Do Not Contact ({counts.do_not_contact})</option>
          </select>
        </div>
      </div>

      {/* Lead Dossiers List */}
      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        {filteredItems.length === 0 ? (
          <div className="card" style={{ padding: "40px", textAlign: "center", color: "var(--text-muted)" }}>
            No leads match the selected search and filter criteria.
          </div>
        ) : (
          filteredItems.map((leadItem) => (
            <div
              key={leadItem.id}
              className="card"
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "14px",
                borderLeft: `4px solid ${
                  leadItem.final_outcome === "INTERESTED" || leadItem.final_outcome === "CONVERTED"
                    ? "var(--success)"
                    : leadItem.final_outcome === "DO_NOT_CONTACT"
                    ? "var(--danger)"
                    : "var(--border)"
                }`,
              }}
            >
              {/* Header Row */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <h3 style={{ fontSize: "16px", fontWeight: 700 }}>{leadItem.lead_name}</h3>
                    <StatusBadge status={leadItem.final_outcome} />
                  </div>

                  <div style={{ display: "flex", gap: "16px", marginTop: "6px", fontSize: "12px", color: "var(--text-secondary)", flexWrap: "wrap" }}>
                    {leadItem.email && (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                        <Mail size={13} color="var(--text-muted)" />
                        {leadItem.email}
                      </span>
                    )}
                    {leadItem.phone && (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                        <Phone size={13} color="var(--text-muted)" />
                        {leadItem.phone}
                      </span>
                    )}
                    {leadItem.company_website && (
                      <a
                        href={leadItem.company_website}
                        target="_blank"
                        rel="noreferrer"
                        style={{ display: "inline-flex", alignItems: "center", gap: "4px", color: "var(--info)" }}
                      >
                        <Globe size={13} />
                        {leadItem.company_website.replace(/^https?:\/\//, "")}
                      </a>
                    )}
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <div style={{ display: "flex", gap: "4px" }}>
                    {leadItem.channels_used.map((c) => (
                      <ChannelBadge key={c} channel={c} />
                    ))}
                  </div>

                  <Link
                    to={`/reports/leads/${leadItem.lead_id}`}
                    className="btn-secondary"
                    style={{ height: "32px", padding: "0 10px", fontSize: "12px" }}
                  >
                    Lead 360°
                    <ChevronRight size={14} />
                  </Link>
                </div>
              </div>

              {/* Approach Timeline */}
              <div style={{ backgroundColor: "var(--surface-subtle)", padding: "10px 14px", borderRadius: "var(--radius-md)", fontSize: "13px" }}>
                <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>Approach: </span>
                <span style={{ color: "var(--text-secondary)" }}>{leadItem.approach_summary}</span>
              </div>

              {/* Conversation Synthesis */}
              <div style={{ fontSize: "13px", lineHeight: "1.5" }}>
                <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>Conversation Synthesis: </span>
                <span style={{ color: "var(--text-secondary)" }}>{leadItem.conversation_summary}</span>
              </div>

              {/* Outcome Reason & Evidence */}
              <div style={{ fontSize: "13px", lineHeight: "1.5" }}>
                <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>Justification & Evidence: </span>
                <span style={{ color: "var(--text-secondary)" }}>{leadItem.outcome_reason}</span>
              </div>

              {/* Recommended Action */}
              {leadItem.recommended_next_action && (
                <div
                  style={{
                    backgroundColor: "rgba(198, 241, 53, 0.15)",
                    border: "1px solid rgba(31, 90, 58, 0.2)",
                    padding: "8px 12px",
                    borderRadius: "var(--radius-md)",
                    fontSize: "12.5px",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <span style={{ fontWeight: 700, color: "var(--brand-deep)" }}>Recommended Next Action:</span>
                  <span style={{ color: "var(--text-primary)" }}>{leadItem.recommended_next_action}</span>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};
