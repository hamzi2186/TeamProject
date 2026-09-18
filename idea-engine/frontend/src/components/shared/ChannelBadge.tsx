import { Mail, MessageSquare, Phone } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { Channel } from "@/types/reports";

interface ChannelBadgeProps {
  channel: Channel;
}

const CHANNEL_META: Record<Channel, { label: string; icon: typeof Phone }> = {
  CALL: { label: "Call", icon: Phone },
  SMS: { label: "SMS", icon: MessageSquare },
  EMAIL: { label: "Email", icon: Mail },
};

export function ChannelBadge({ channel }: ChannelBadgeProps) {
  const meta = CHANNEL_META[channel] ?? { label: channel, icon: MessageSquare };
  const Icon = meta.icon;

  return (
    <Badge variant="outline" aria-label={`Channel: ${meta.label}`}>
      <Icon className="size-3 text-muted-foreground" />
      {meta.label}
    </Badge>
  );
}