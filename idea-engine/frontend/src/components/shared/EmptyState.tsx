import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  action?: ReactNode;
}

export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
      {Icon && (
        <div className="mb-2 flex size-10 items-center justify-center rounded-md border border-border bg-surface-subtle">
          <Icon className="size-5 text-muted-foreground" />
        </div>
      )}
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      <p className="max-w-md text-[13px] text-secondary-foreground">{description}</p>
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}