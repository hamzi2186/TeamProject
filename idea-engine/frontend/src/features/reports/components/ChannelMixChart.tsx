import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import {
  ChartTooltip,
  CHART_COLORS,
  ChartEmpty,
} from "@/features/reports/components/chart-base";
import type { Channel } from "@/types/reports";

interface ChannelMixChartProps {
  channels: Channel[];
}

export function ChannelMixChart({ channels }: ChannelMixChartProps) {
  const counts = new Map<string, number>();
  for (const channel of channels) {
    counts.set(channel, (counts.get(channel) ?? 0) + 1);
  }

  const data = Array.from(counts.entries())
    .map(([channel, value], index) => ({
      name: channel.charAt(0) + channel.slice(1).toLowerCase(),
      value,
      fill: [CHART_COLORS.brandDeep, CHART_COLORS.success, CHART_COLORS.warning, CHART_COLORS.info][index % 4],
    }))
    .sort((a, b) => b.value - a.value);

  if (data.length === 0) {
    return <ChartEmpty>No channel data to display.</ChartEmpty>;
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          innerRadius="52%"
          outerRadius="80%"
          paddingAngle={3}
          strokeWidth={1}
          stroke="#FFFFFF"
        >
          {data.map((entry, index) => (
            <Cell key={`${entry.name}-${index}`} fill={entry.fill} />
          ))}
        </Pie>
        <Tooltip content={<ChartTooltip />} />
      </PieChart>
    </ResponsiveContainer>
  );
}