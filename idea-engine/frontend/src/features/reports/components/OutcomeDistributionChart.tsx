import {
  Bar,
  BarChart,
  Cell,
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
import type { IdeaReportSummaryCounts } from "@/types/reports";

interface OutcomeDistributionChartProps {
  counts: IdeaReportSummaryCounts;
}

interface Slice {
  key: string;
  label: string;
  value: number;
  fill: string;
}

function buildSlices(counts: IdeaReportSummaryCounts): Slice[] {
  return [
    { key: "interested", label: "Interested", value: counts.interested, fill: CHART_COLORS.brand },
    { key: "converted", label: "Converted", value: counts.converted, fill: CHART_COLORS.success },
    { key: "follow_up_required", label: "Follow-up required", value: counts.follow_up_required, fill: CHART_COLORS.warning },
    { key: "not_interested", label: "Not interested", value: counts.not_interested, fill: CHART_COLORS.mutedLight },
    { key: "do_not_contact", label: "Do not contact", value: counts.do_not_contact, fill: CHART_COLORS.danger },
    { key: "other", label: "No answer / no response / other", value: counts.no_answer + counts.no_response + counts.contacting + counts.failed + counts.new, fill: CHART_COLORS.info },
  ].filter((slice) => slice.value > 0);
}

export function OutcomeDistributionChart({ counts }: OutcomeDistributionChartProps) {
  const data = buildSlices(counts);

  if (data.length === 0) {
    return <ChartEmpty>No outcome data to display.</ChartEmpty>;
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <XAxis
          dataKey="label"
          type="category"
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 11, fill: CHART_COLORS.muted }}
          dy={4}
          interval={0}
          tickFormatter={(label: string) => (label.length > 16 ? `${label.slice(0, 15)}…` : label)}
        />
        <YAxis type="number" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: CHART_COLORS.muted }} allowDecimals={false} />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(241,239,233,0.5)" }} />
        <Bar dataKey="value" name="Leads" radius={4}>
          {data.map((slice, index) => (
            <Cell key={`${slice.key}-${index}`} fill={slice.fill} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}