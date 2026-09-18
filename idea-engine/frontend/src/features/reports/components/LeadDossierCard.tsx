import { Link } from "react-router-dom";
import { ArrowLeft, ArrowRight, Globe, Mail, Phone, Target } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ChannelBadge } from "@/components/shared/ChannelBadge";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { cn } from "@/lib/utils";
import type { LeadReportItem } from "@/types/reports";

interface LeadDossierCardProps {
  item: LeadReportItem;
}

function accentFor(outcome: string): string {
  if (outcome === "INTERESTED" || outcome === "CONVERTED") return "border-l-success";
  if (outcome === "DO_NOT_CONTACT" || outcome === "FAILED") return "border-l-danger";
  return "border-l-border";
}

export function LeadDossierCard({ item }: LeadDossierCardProps) {
  return (
    <article
      className={cn(
        "flex flex-col gap-3.5 rounded-lg border border-l-4 border-border bg-card p-5 shadow-sm",
        accentFor(item.final_outcome),
      )}
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2.5">
            <h3 className="text-sm font-semibold text-foreground">{item.lead_name}</h3>
            <StatusBadge status={item.final_outcome} />
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-secondary-foreground">
            {item.email && (
              <span className="inline-flex items-center gap-1.5">
                <Mail className="size-3.5 text-muted-foreground" />
                {item.email}
              </span>
            )}
            {item.phone && (
              <span className="inline-flex items-center gap-1.5">
                <Phone className="size-3.5 text-muted-foreground" />
                {item.phone}
              </span>
            )}
            {item.company_website && (
              <a
                href={item.company_website}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 text-info hover:underline"
              >
                <Globe className="size-3.5" />
                {item.company_website.replace(/^https?:\/\//, "")}
              </a>
            )}
            {item.campaigns.length > 0 && (
              <span className="inline-flex items-center gap-1.5">
                <Target className="size-3.5 text-muted-foreground" />
                {item.campaigns.join(", ")}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <div className="flex flex-wrap gap-1.5">
            {item.channels_used.map((channel) => (
              <ChannelBadge key={channel} channel={channel} />
            ))}
          </div>
          <Button variant="secondary" size="sm" asChild>
            <Link to={`/reports/leads/${item.lead_id}`}>
              View journey
              <ArrowRight className="size-3.5" />
            </Link>
          </Button>
        </div>
      </header>

      <section className="rounded-md bg-surface-subtle px-3.5 py-2.5 text-[13px]">
        <span className="font-semibold text-foreground">Approach: </span>
        <span className="text-secondary-foreground">{item.approach_summary}</span>
      </section>

      <section className="text-[13px] leading-relaxed">
        <span className="font-semibold text-foreground">Conversation synthesis: </span>
        <span className="text-secondary-foreground">{item.conversation_summary}</span>
      </section>

      <section className="text-[13px] leading-relaxed">
        <span className="font-semibold text-foreground">Justification and evidence: </span>
        <span className="text-secondary-foreground">{item.outcome_reason}</span>
      </section>

      {item.recommended_next_action && (
        <section className="flex items-start gap-2 rounded-md border border-brand-deep/20 bg-brand/10 px-3 py-2.5 text-[13px]">
          <span className="font-semibold text-brand-deep">Next action:</span>
          <span className="text-foreground">{item.recommended_next_action}</span>
        </section>
      )}

      <footer className="flex items-center gap-1 text-[12px] text-muted-foreground">
        <ArrowLeft className="size-3.5" />
        See the full cross-channel timeline on the lead journey page.
      </footer>
    </article>
  );
}