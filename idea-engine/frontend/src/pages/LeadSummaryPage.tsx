import { Link, useParams } from "react-router-dom";
import { Activity, ArrowLeft, Globe, Mail, Phone, Target } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ChannelBadge } from "@/components/shared/ChannelBadge";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingSkeleton } from "@/components/shared/LoadingSkeleton";
import { Timeline } from "@/components/shared/Timeline";
import { useLeadJourney } from "@/features/reports/hooks/use-reports";

export function LeadSummaryPage() {
  const { leadId } = useParams<{ leadId: string }>();
  const { data: journey, isLoading, isError, refetch } = useLeadJourney(leadId);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Lead journey" description="Loading lead intelligence..." />
        <LoadingSkeleton variant="cards" rows={3} />
      </div>
    );
  }

  if (isError || !journey) {
    return (
      <div className="rounded-lg border border-border bg-card shadow-sm">
        <ErrorState
          title="Could not load this lead"
          description="The lead journey could not be fetched. Please try again."
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

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start gap-3">
        <Button variant="secondary" size="icon" asChild aria-label="Back to reports">
          <Link to="/reports">
            <ArrowLeft className="size-4" />
          </Link>
        </Button>
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-[28px] font-semibold leading-tight tracking-tight text-foreground">
              {journey.lead_name}
            </h1>
            <StatusBadge status={journey.final_outcome} />
          </div>
          <p className="mt-1 text-[13px] text-muted-foreground">
            Lead journey across calling, SMS, and email outreach.
          </p>
        </div>
      </div>

      <div className="grid items-start gap-5 lg:grid-cols-3">
        <div className="flex flex-col gap-4 lg:col-span-1">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle>Lead contact</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5 text-[13px]">
              {journey.email && (
                <p className="flex items-center gap-2">
                  <Mail className="size-4 shrink-0 text-muted-foreground" />
                  <span className="break-all">{journey.email}</span>
                </p>
              )}
              {journey.phone && (
                <p className="flex items-center gap-2">
                  <Phone className="size-4 shrink-0 text-muted-foreground" />
                  {journey.phone}
                </p>
              )}
              {journey.website_url && (
                <p className="flex items-center gap-2">
                  <Globe className="size-4 shrink-0 text-muted-foreground" />
                  <a
                    href={journey.website_url}
                    target="_blank"
                    rel="noreferrer"
                    className="break-all text-info hover:underline"
                  >
                    {journey.website_url}
                  </a>
                </p>
              )}
              {journey.campaigns.length > 0 && (
                <p className="flex items-center gap-2">
                  <Target className="size-4 shrink-0 text-muted-foreground" />
                  {journey.campaigns.join(", ")}
                </p>
              )}

              <div className="pt-2">
                <p className="mb-1.5 text-xs font-medium text-muted-foreground">Channels engaged</p>
                <div className="flex flex-wrap gap-1.5">
                  {journey.channels_used.length === 0 ? (
                    <span className="text-[12px] text-muted-foreground">None recorded yet</span>
                  ) : (
                    journey.channels_used.map((channel) => (
                      <ChannelBadge key={channel} channel={channel} />
                    ))
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle>Intelligence evaluation</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3.5 text-[13px]">
              <div>
                <h3 className="text-xs font-semibold text-muted-foreground">Approach timeline</h3>
                <p className="mt-1 leading-relaxed text-secondary-foreground">
                  {journey.approach_summary || "Outreach not yet initiated."}
                </p>
              </div>
              <div>
                <h3 className="text-xs font-semibold text-muted-foreground">Conversation synthesis</h3>
                <p className="mt-1 leading-relaxed text-secondary-foreground">
                  {journey.conversation_summary || "No active conversation turns."}
                </p>
              </div>
              <div>
                <h3 className="text-xs font-semibold text-muted-foreground">Outcome evidence</h3>
                <p className="mt-1 leading-relaxed text-secondary-foreground">
                  {journey.outcome_reason}
                </p>
              </div>
              {journey.recommended_next_action && (
                <div className="rounded-md border border-brand-deep/20 bg-brand/10 p-3">
                  <p className="text-xs font-semibold text-brand-deep">Recommended action</p>
                  <p className="mt-1 text-[13px] text-foreground">{journey.recommended_next_action}</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
            <CardTitle className="flex items-center gap-2">
              <Activity className="size-4 text-brand-deep" aria-hidden />
              Cross-channel journey timeline
            </CardTitle>
            <span className="text-xs text-muted-foreground">
              {journey.timeline.length} touchpoint{journey.timeline.length === 1 ? "" : "s"}
            </span>
          </CardHeader>
          <CardContent>
            {journey.timeline.length === 0 ? (
              <EmptyState
                icon={Activity}
                title="No touchpoints recorded"
                description="This lead has no persisted calling, SMS, or email interactions yet."
              />
            ) : (
              <Timeline events={journey.timeline} />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}