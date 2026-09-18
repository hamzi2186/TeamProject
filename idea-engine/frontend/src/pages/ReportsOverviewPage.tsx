import { useCallback } from "react";
import { Link } from "react-router-dom";
import { Download, FileText, Play } from "lucide-react";

import { getDownloadUrl } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/shared/PageHeader";
import { MetricCard } from "@/components/shared/MetricCard";
import { ChartCard } from "@/components/shared/ChartCard";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingSkeleton } from "@/components/shared/LoadingSkeleton";
import { DataTable, type DataTableColumn } from "@/components/shared/DataTable";
import { Reveal } from "@/components/shared/Reveal";
import { TrendLineChart } from "@/features/reports/components/TrendLineChart";
import { OutcomeDistributionChart } from "@/features/reports/components/OutcomeDistributionChart";
import { useDailyReports, useGenerateDailyReport } from "@/features/reports/hooks/use-reports";
import { cn } from "@/lib/utils";
import type { IdeaReportRun } from "@/types/reports";

const NO_RESPONSE = [
  { label: "Interested", key: "interested" as const, className: "bg-success/10 text-success border border-success/25" },
  { label: "Converted", key: "converted" as const, className: "bg-brand-deep/10 text-brand-deep border border-brand-deep/25" },
  { label: "Follow-up", key: "follow_up_required" as const, className: "bg-warning/10 text-warning border border-warning/25" },
  { label: "Not interested", key: "not_interested" as const, className: "bg-surface-subtle text-secondary-foreground border border-border" },
  { label: "DNC", key: "do_not_contact" as const, className: "bg-danger/10 text-danger border border-danger/25" },
];

export function ReportsOverviewPage() {
  const { data: reports, isLoading, isError, refetch } = useDailyReports(1, 30);
  const generateMutation = useGenerateDailyReport();

  const latestRun = reports && reports.length > 0 ? reports[0] : null;
  const counts = latestRun?.summary_counts;

  const handleGenerate = useCallback(
    () => generateMutation.mutate(undefined),
    [generateMutation],
  );

  const columns: DataTableColumn<IdeaReportRun>[] = [
    {
      key: "date",
      header: "Report date",
      render: (report) => (
        <span className="font-semibold text-foreground">{report.report_date}</span>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (report) => <StatusBadge status={report.status} />,
    },
    {
      key: "total",
      header: "Total leads",
      render: (report) => <span className="font-medium">{report.total_leads}</span>,
    },
    {
      key: "outcomes",
      header: "Outcome breakdown",
      render: (report) => {
        const summary = report.summary_counts;
        const visible = NO_RESPONSE.filter((item) => summary[item.key] > 0);
        if (visible.length === 0) return <span className="text-muted-foreground">No outcomes</span>;
        return (
          <div className="flex flex-wrap gap-1.5">
            {visible.map((item) => (
              <span key={item.key} className={cn("rounded px-1.5 py-0.5 text-[11px] font-medium", item.className)}>
                {summary[item.key]} {item.label}
              </span>
            ))}
          </div>
        );
      },
    },
    {
      key: "generated",
      header: "Generated time",
      render: (report) => (
        <span className="text-muted-foreground">
          {report.generated_at ? new Date(report.generated_at).toLocaleString() : "Pending"}
        </span>
      ),
    },
    {
      key: "actions",
      header: "Actions",
      align: "right",
      render: (report) => (
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" asChild>
            <Link to={`/reports/${report.id}`}>View detail</Link>
          </Button>
          <Button size="sm" asChild>
            <a href={getDownloadUrl(report.id)} download>
              <Download className="size-3.5" />
              Download DOCX
            </a>
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Daily lead reports"
        description="Cross-channel lead intelligence aggregated every day at 00:00 UTC."
        actions={
          <Button
            variant={reports && reports.length > 0 ? "secondary" : "default"}
            onClick={handleGenerate}
            disabled={generateMutation.isPending}
          >
            {generateMutation.isPending ? (
              <>
                <Play className="size-4 animate-spin" aria-hidden />
                Generating...
              </>
            ) : (
              <>
                <Play className="size-4" aria-hidden />
                Generate report
              </>
            )}
          </Button>
        }
      />

      {isLoading ? (
        <LoadingSkeleton variant="table" rows={7} />
      ) : isError ? (
        <div className="rounded-lg border border-border bg-card shadow-sm">
          <ErrorState
            title="Could not load reports"
            description="The report list could not be fetched. Please try again."
            onRetry={() => refetch()}
          />
        </div>
      ) : (
        <>
          <Reveal className="grid auto-rows-fr grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <MetricCard label="Total reports" value={reports?.length ?? 0} subtext="Generated to date" />
            <MetricCard label="Latest reviewed leads" value={latestRun?.total_leads ?? 0} subtext={latestRun ? `Date: ${latestRun.report_date}` : "No reports yet"} />
            <MetricCard label="Latest interested" value={counts?.interested ?? 0} accentColor="#1F6A45" subtext="High conversion potential" />
            <MetricCard label="Latest converted" value={counts?.converted ?? 0} accentColor="#1F5A3A" subtext="Deals closed" />
            <MetricCard label="Follow-ups required" value={counts?.follow_up_required ?? 0} accentColor="#C98924" subtext="Action needed" />
            <MetricCard label="Do not contact" value={counts?.do_not_contact ?? 0} accentColor="#C93A32" subtext="Suppressed leads" />
          </Reveal>

          {(reports && reports.length === 0) || !reports ? (
            <div className="rounded-lg border border-border bg-card shadow-sm">
              <EmptyState
                icon={FileText}
                title="No reports generated yet"
                description="Generate today's report to compile every lead's calling, SMS, and email history into a DOCX dossier."
                action={
                  <Button size="sm" onClick={handleGenerate} disabled={generateMutation.isPending}>
                    <Play className="size-3.5" aria-hidden />
                    Generate first report
                  </Button>
                }
              />
            </div>
          ) : (
            <>
              {reports.length > 1 && (
                <Reveal className="grid gap-4 lg:grid-cols-2">
                  <ChartCard title="Outcome trend" description="Interested, converted, and follow-up leads over the last reports.">
                    <TrendLineChart reports={reports} />
                  </ChartCard>
                  <ChartCard title="Latest outcome mix" description={`Distribution for the report of ${latestRun?.report_date}`}>
                    {counts ? <OutcomeDistributionChart counts={counts} /> : null}
                  </ChartCard>
                </Reveal>
              )}

              <Reveal className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-[18px] font-semibold tracking-tight text-foreground">Report history</h2>
                  <Badge variant="outline">DOCX ready to download</Badge>
                </div>
                <DataTable
                  aria-label="Report history"
                  columns={columns}
                  rows={reports}
                  getRowKey={(report) => report.id}
                />
              </Reveal>
            </>
          )}
        </>
      )}
    </div>
  );
}