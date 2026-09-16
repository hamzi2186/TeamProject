import React from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Download,
  FileText,
  Play,
  Calendar,
  Clock,
  ArrowRight,
} from "lucide-react";

import { fetchDailyReports, generateDailyReport } from "../api/reports";
import { getDownloadUrl } from "../api/client";
import { MetricCard } from "../components/MetricCard";
import { StatusBadge } from "../components/StatusBadge";

export const ReportsOverviewPage: React.FC = () => {
  const queryClient = useQueryClient();

  const { data: reports, isLoading, isError, error } = useQuery({
    queryKey: ["dailyReports"],
    queryFn: () => fetchDailyReports(1, 30),
  });

  const generateMutation = useMutation({
    mutationFn: (targetDate?: string) => generateDailyReport(targetDate),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dailyReports"] });
    },
  });

  const handleGenerate = (targetDate?: string) => {
    generateMutation.mutate(targetDate || undefined);
  };

  // Calculate cumulative stats across available runs
  const totalReports = reports?.length || 0;
  const latestRun = reports && reports.length > 0 ? reports[0] : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* Page Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <h1 style={{ fontSize: "26px", fontWeight: 700, letterSpacing: "-0.02em", color: "var(--text-primary)" }}>
            Daily Lead Intelligence Reports
          </h1>
          <p style={{ fontSize: "14px", color: "var(--text-secondary)", marginTop: "4px" }}>
            Aggregated cross-channel insights from Calling, SMS, and Mailer outreach.
          </p>
        </div>

        <div style={{ display: "flex", gap: "10px" }}>
          <button
            className="btn-primary"
            onClick={() => handleGenerate()}
            disabled={generateMutation.isPending}
          >
            {generateMutation.isPending ? (
              <>
                <Clock size={16} className="animate-spin" />
                Generating Report...
              </>
            ) : (
              <>
                <Play size={15} fill="currentColor" />
                Generate Today's Report
              </>
            )}
          </button>
        </div>
      </div>

      {/* KPI Overview Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "14px" }}>
        <MetricCard
          label="Total Reports"
          value={totalReports}
          subtext="Generated to date"
        />
        <MetricCard
          label="Latest Reviewed Leads"
          value={latestRun ? latestRun.total_leads : 0}
          subtext={latestRun ? `Date: ${latestRun.report_date}` : "No reports yet"}
        />
        <MetricCard
          label="Latest Interested"
          value={latestRun ? latestRun.summary_counts.interested : 0}
          accentColor="var(--success)"
          subtext="High conversion potential"
        />
        <MetricCard
          label="Latest Converted"
          value={latestRun ? latestRun.summary_counts.converted : 0}
          accentColor="var(--brand-deep)"
          subtext="Deals closed"
        />
        <MetricCard
          label="Follow-ups Required"
          value={latestRun ? latestRun.summary_counts.follow_up_required : 0}
          accentColor="var(--warning)"
          subtext="Action needed"
        />
        <MetricCard
          label="Do Not Contact"
          value={latestRun ? latestRun.summary_counts.do_not_contact : 0}
          accentColor="var(--danger)"
          subtext="Suppressed leads"
        />
      </div>

      {/* Reports Table Section */}
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontWeight: 600, fontSize: "15px" }}>Report History</span>
          <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
            Download ready (.docx)
          </span>
        </div>

        {isLoading ? (
          <div style={{ padding: "40px", textAlign: "center", color: "var(--text-muted)" }}>
            Loading reports history...
          </div>
        ) : isError ? (
          <div style={{ padding: "40px", textAlign: "center", color: "var(--danger)" }}>
            Failed to load reports: {(error as Error).message}
          </div>
        ) : !reports || reports.length === 0 ? (
          <div style={{ padding: "48px 24px", textAlign: "center" }}>
            <FileText size={36} color="var(--text-muted)" style={{ margin: "0 auto 12px", display: "block" }} />
            <h3 style={{ fontSize: "16px", fontWeight: 600, color: "var(--text-primary)" }}>No reports generated yet</h3>
            <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginTop: "4px", maxWidth: "420px", margin: "4px auto 16px" }}>
              Click "Generate Today's Report" above or run the seed script to compile lead interactions across Calling, SMS, and Mailer.
            </p>
            <button className="btn-secondary" onClick={() => handleGenerate()}>
              Generate First Report
            </button>
          </div>
        ) : (
          <div className="table-container" style={{ border: "none", borderRadius: 0 }}>
            <table>
              <thead>
                <tr>
                  <th>Report Date</th>
                  <th>Status</th>
                  <th>Total Leads</th>
                  <th>Outcome Breakdown</th>
                  <th>Generated Time</th>
                  <th style={{ textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((report) => {
                  const counts = report.summary_counts;
                  return (
                    <tr key={report.id}>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <Calendar size={15} color="var(--text-muted)" />
                          <span style={{ fontWeight: 600 }}>{report.report_date}</span>
                        </div>
                      </td>
                      <td>
                        <StatusBadge status={report.status} />
                      </td>
                      <td style={{ fontWeight: 500 }}>
                        {report.total_leads} leads
                      </td>
                      <td>
                        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                          {counts.interested > 0 && (
                            <span style={{ fontSize: "11px", color: "var(--success)", backgroundColor: "rgba(31, 106, 69, 0.1)", padding: "1px 6px", borderRadius: "3px", fontWeight: 600 }}>
                              {counts.interested} Interested
                            </span>
                          )}
                          {counts.converted > 0 && (
                            <span style={{ fontSize: "11px", color: "var(--brand-deep)", backgroundColor: "rgba(31, 90, 58, 0.1)", padding: "1px 6px", borderRadius: "3px", fontWeight: 600 }}>
                              {counts.converted} Converted
                            </span>
                          )}
                          {counts.follow_up_required > 0 && (
                            <span style={{ fontSize: "11px", color: "var(--warning)", backgroundColor: "rgba(201, 137, 36, 0.1)", padding: "1px 6px", borderRadius: "3px", fontWeight: 600 }}>
                              {counts.follow_up_required} Follow-up
                            </span>
                          )}
                          {counts.not_interested > 0 && (
                            <span style={{ fontSize: "11px", color: "var(--text-muted)", backgroundColor: "var(--surface-subtle)", padding: "1px 6px", borderRadius: "3px" }}>
                              {counts.not_interested} Not Int.
                            </span>
                          )}
                          {counts.do_not_contact > 0 && (
                            <span style={{ fontSize: "11px", color: "var(--danger)", backgroundColor: "rgba(201, 58, 50, 0.1)", padding: "1px 6px", borderRadius: "3px" }}>
                              {counts.do_not_contact} DNC
                            </span>
                          )}
                        </div>
                      </td>
                      <td style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                        {report.generated_at ? new Date(report.generated_at).toLocaleString() : "Pending"}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <div style={{ display: "inline-flex", gap: "8px" }}>
                          <Link to={`/reports/${report.id}`} className="btn-secondary" style={{ height: "32px", padding: "0 10px", fontSize: "12px" }}>
                            View Detail
                            <ArrowRight size={13} />
                          </Link>
                          <a
                            href={getDownloadUrl(report.id)}
                            download
                            className="btn-primary"
                            style={{ height: "32px", padding: "0 12px", fontSize: "12px" }}
                          >
                            <Download size={13} />
                            Download DOCX
                          </a>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
