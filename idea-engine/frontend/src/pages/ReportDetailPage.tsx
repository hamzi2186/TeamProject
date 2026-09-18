import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Download, FileText } from "lucide-react";

import { getDownloadUrl } from "@/api/client";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PageHeader } from "@/components/shared/PageHeader";
import { MetricCard } from "@/components/shared/MetricCard";
import { ChartCard } from "@/components/shared/ChartCard";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingSkeleton } from "@/components/shared/LoadingSkeleton";
import { SearchInput } from "@/components/shared/SearchInput";
import { FilterBar } from "@/components/shared/FilterBar";
import { Reveal } from "@/components/shared/Reveal";
import { LeadDossierCard } from "@/features/reports/components/LeadDossierCard";
import { OutcomeDistributionChart } from "@/features/reports/components/OutcomeDistributionChart";
import { ChannelMixChart } from "@/features/reports/components/ChannelMixChart";
import { useReportDetail } from "@/features/reports/hooks/use-reports";

const OUTCOME_OPTIONS: { value: string; label: string }[] = [
  { value: "ALL", label: "All outcomes" },
  { value: "INTERESTED", label: "Interested" },
  { value: "CONVERTED", label: "Converted" },
  { value: "FOLLOW_UP_REQUIRED", label: "Follow-up required" },
  { value: "NOT_INTERESTED", label: "Not interested" },
  { value: "NO_ANSWER", label: "No answer" },
  { value: "NO_RESPONSE", label: "No response" },
  { value: "DO_NOT_CONTACT", label: "Do not contact" },
  { value: "NEW", label: "New" },
  { value: "FAILED", label: "Failed" },
];

export function ReportDetailPage() {
  const { reportId } = useParams<{ reportId: string }>();
  const { data: report, isLoading, isError, refetch } = useReportDetail(reportId);
  const [search, setSearch] = useState("");
  const [outcomeFilter, setOutcomeFilter] = useState("ALL");

  const items = report?.items ?? [];
  const allChannels = useMemo(() => items.flatMap((item) => item.channels_used), [items]);

  const filteredItems = useMemo(() => {
    const term = search.trim().toLowerCase();
    return items.filter((item) => {
      const matchesSearch =
        term === "" ||
        item.lead_name.toLowerCase().includes(term) ||
        (item.company_website ?? "").toLowerCase().includes(term) ||
        (item.email ?? "").toLowerCase().includes(term);
      const matchesOutcome =
        outcomeFilter === "ALL" || item.final_outcome.toUpperCase() === outcomeFilter.toUpperCase();
      return matchesSearch && matchesOutcome;
    });
  }, [items, search, outcomeFilter]);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Lead intelligence report" description="Loading report data..." />
        <LoadingSkeleton variant="cards" rows={4} />
      </div>
    );
  }

  if (isError || !report) {
    return (
      <div className="rounded-lg border border-border bg-card shadow-sm">
        <ErrorState
          title="Could not load this report"
          description="The report detail could not be fetched. Return to the overview or try again."
          onRetry={() => refetch()}
        />
        <div className="pb-6 text-center">
          <Button variant="secondary" size="sm" asChild>
            <Link to="/reports">Back to reports</Link>
          </Button>
        </div>
      </div>
    );
  }

  const counts = report.summary_counts;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <Button variant="secondary" size="icon" asChild aria-label="Back to reports">
            <Link to="/reports">
              <ArrowLeft className="size-4" />
            </Link>
          </Button>
          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-[28px] font-semibold leading-tight tracking-tight text-foreground">
                Lead intelligence report
              </h1>
              <StatusBadge status={report.status} />
            </div>
            <p className="mt-1 text-[13px] text-muted-foreground">
              Report date {report.report_date} · {report.total_leads} leads reviewed
              {report.generated_at ? ` · generated ${new Date(report.generated_at).toLocaleString()}` : ""}
            </p>
          </div>
        </div>
        <Button asChild>
          <a href={getDownloadUrl(report.id)} download>
            <Download className="size-4" aria-hidden />
            Download full DOCX
          </a>
        </Button>
      </div>

      <Reveal className="grid auto-rows-fr grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        <MetricCard label="Total leads" value={counts.total_leads} />
        <MetricCard label="Interested" value={counts.interested} accentColor="#1F6A45" />
        <MetricCard label="Converted" value={counts.converted} accentColor="#1F5A3A" />
        <MetricCard label="Follow-up" value={counts.follow_up_required} accentColor="#C98924" />
        <MetricCard label="Not interested" value={counts.not_interested} />
        <MetricCard label="No answer / response" value={counts.no_answer + counts.no_response} />
        <MetricCard label="Do not contact" value={counts.do_not_contact} accentColor="#C93A32" />
      </Reveal>

      {items.length > 0 && (
        <Reveal className="grid gap-4 lg:grid-cols-2">
          <ChartCard title="Outcome distribution" description="Canonical lead outcomes assigned by the evaluation engine.">
            <OutcomeDistributionChart counts={counts} />
          </ChartCard>
          <ChartCard title="Channel mix" description="Touchpoint channels used across reviewed leads.">
            <ChannelMixChart channels={allChannels} />
          </ChartCard>
        </Reveal>
      )}

      <FilterBar
        controls={
          <>
            <SearchInput
              value={search}
              onChange={setSearch}
              placeholder="Search by lead name, website, or email"
              className="w-full sm:max-w-sm"
              aria-label="Search leads"
            />
            <Select value={outcomeFilter} onValueChange={setOutcomeFilter}>
              <SelectTrigger className="w-full sm:w-[220px]" aria-label="Filter by outcome">
                <SelectValue placeholder="All outcomes" />
              </SelectTrigger>
              <SelectContent>
                {OUTCOME_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </>
        }
      />

      {filteredItems.length === 0 ? (
        items.length === 0 ? (
          <div className="rounded-lg border border-border bg-card shadow-sm">
            <EmptyState
              icon={FileText}
              title="No leads in this report"
              description="This report run did not capture any lead interactions."
            />
          </div>
        ) : (
          <div className="rounded-lg border border-border bg-card shadow-sm">
            <EmptyState
              icon={FileText}
              title="No leads match your filters"
              description="Try a different search term or outcome filter."
            />
          </div>
        )
      ) : (
        <ul className="flex flex-col gap-4">
          {filteredItems.map((item) => (
            <li key={item.id}>
              <Reveal>
                <LeadDossierCard item={item} />
              </Reveal>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}