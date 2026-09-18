import {
  CartesianGrid,
  Line,
  LineChart,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import {
  ChartTooltip,
  CHART_COLORS,
  ChartEmpty,
} from "@/features/reports/components/chart-base";
import type { IdeaReportRun } from "@/types/reports";

interface TrendLineChartProps {
  reports: IdeaReportRun[];
}

export function TrendLineChart({ reports }: TrendLineChartProps) {
  const ordered = [...reports].sort(
    (a, b) => new Date(a.report_date).getTime() - new Date(b.report_date).getTime(),
  );
  const recent = ordered.slice(-8);

  if (recent.length === 0) {
    return <ChartEmpty>No report history to chart.</ChartEmpty>;
  }

  const data = recent.map((report) => ({
    date: report.report_date.slice(5),
    Interested: report.summary_counts.interested,
    Converted: report.summary_counts.converted,
    "Follow-up": report.summary_counts.follow_up_required,
  }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid stroke="#EEEBE4" strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="date"
          type="category"
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 11, fill: CHART_COLORS.muted }}
          dy={4}
        />
        <YAxis type="number" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: CHART_COLORS.muted }} allowDecimals={false} />
        <Tooltip content={<ChartTooltip />} />
        <Line
          type="monotone"
          dataKey="Interested"
          stroke={CHART_COLORS.brand}
          strokeWidth={2.5}
          dot={{ r: 2.5, fill: CHART_COLORS.brand }}
          activeDot={{ r: 4 }}
        />
        <Line type="monotone" dataKey="Converted" stroke={CHART_COLORS.success} strokeWidth={2} dot={{ r: 2.5, fill: CHART_COLORS.success }} activeDot={{ r: 4 }} />
        <Line type="monotone" dataKey="Follow-up" stroke={CHART_COLORS.mutedLight} strokeWidth={2} dot={{ r: 2.5, fill: CHART_COLORS.mutedLight }} activeDot={{ r: 4 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}