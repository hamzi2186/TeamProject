import type { ReactNode } from "react";
import { Filter } from "lucide-react";

interface FilterBarProps {
  controls: ReactNode;
}

export function FilterBar({ controls }: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card p-4 shadow-sm">
      <span className="inline-flex items-center gap-2 text-xs font-medium text-muted-foreground">
        <Filter className="size-3.5" />
        Filters
      </span>
      <div className="flex flex-1 flex-wrap items-center gap-3">{controls}</div>
    </div>
  );
}