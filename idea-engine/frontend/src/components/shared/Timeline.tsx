import { ArrowDownLeft, ArrowUpRight, Clock } from "lucide-react";

import { ChannelBadge } from "@/components/shared/ChannelBadge";
import { cn } from "@/lib/utils";
import type { TimelineEvent } from "@/types/reports";

interface TimelineProps {
  events: TimelineEvent[];
}

export function Timeline({ events }: TimelineProps) {
  if (!events || events.length === 0) {
    return (
      <p className="py-6 text-center text-[13px] text-muted-foreground">
        No communication touchpoints recorded yet.
      </p>
    );
  }

  return (
    <ol className="space-y-3">
      {events.map((event, index) => {
        const isInbound = event.direction === "INBOUND";
        const dateObj = new Date(event.timestamp);
        const timeFormatted = dateObj.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });
        const dateFormatted = dateObj.toLocaleDateString([], { month: "short", day: "numeric" });

        return (
          <li
            key={event.id || String(index)}
            className={cn(
              "flex gap-3.5 rounded-md border p-3.5",
              isInbound ? "border-success/25 bg-success/[0.06]" : "border-border bg-card",
            )}
          >
            <div className="flex min-w-16 flex-col items-center gap-1">
              <span
                className={cn(
                  "flex size-7 items-center justify-center rounded-full",
                  isInbound ? "bg-primary text-primary-foreground" : "bg-surface-subtle text-secondary-foreground",
                )}
                aria-hidden
              >
                {isInbound ? <ArrowDownLeft className="size-4" /> : <ArrowUpRight className="size-4" />}
              </span>
              <span className="text-[11px] font-semibold text-foreground">{timeFormatted}</span>
              <span className="text-[10px] text-muted-foreground">{dateFormatted}</span>
            </div>

            <div className="flex flex-1 flex-col gap-1.5">
              <div className="flex flex-wrap items-center gap-2">
                <ChannelBadge channel={event.channel} />
                <span
                  className={cn(
                    "text-[11px] font-semibold uppercase tracking-wide",
                    isInbound ? "text-brand-deep" : "text-secondary-foreground",
                  )}
                >
                  {event.direction === "INBOUND" ? "Inbound" : "Outbound"}
                </span>
                {event.duration_seconds !== null && event.duration_seconds !== undefined && (
                  <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                    <Clock className="size-3" />
                    {event.duration_seconds}s
                  </span>
                )}
                {event.delivery_status && (
                  <span className="rounded-sm bg-surface-subtle px-1.5 py-0.5 text-[10px] text-muted-foreground">
                    {event.delivery_status}
                  </span>
                )}
              </div>

              {event.subject && (
                <p className="text-[13px] font-semibold text-foreground">{event.subject}</p>
              )}
              <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-foreground">
                {event.content}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}