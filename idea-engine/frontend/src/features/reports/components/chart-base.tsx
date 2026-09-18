import type { ReactNode } from "react";

export const CHART_COLORS = {
  brand: "#C6F135",
  brandDeep: "#1F5A3A",
  success: "#1F6A45",
  warning: "#C98924",
  danger: "#C93A32",
  info: "#2D5FA8",
  muted: "#9A9D94",
  mutedLight: "#C9C7BF",
};

interface ChartTooltipProps {
  active?: boolean;
  label?: string | number;
  payload?: ReadonlyArray<{ name?: string; value?: number | string; color?: string; stroke?: string }>;
}

export function ChartTooltip({ active, label, payload }: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;

  return (
    <div className="rounded-md border border-border bg-card px-3 py-2 text-xs shadow-sm">
      {label !== undefined && <p className="mb-1 font-semibold text-foreground">{label}</p>}
      <div className="space-y-0.5">
        {payload.map((entry, index) => (
          <p key={`${entry.name}-${index}`} className="flex items-center gap-1.5 text-muted-foreground">
            <span
              aria-hidden
              className="inline-block size-2 rounded-full"
              style={{ background: entry.color ?? entry.stroke ?? CHART_COLORS.brandDeep }}
            />
            <span>
              {entry.name}: <span className="font-semibold text-foreground">{entry.value}</span>
            </span>
          </p>
        ))}
      </div>
    </div>
  );
}

export function ChartEmpty({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-full items-center justify-center text-[13px] text-muted-foreground">
      {children}
    </div>
  );
}