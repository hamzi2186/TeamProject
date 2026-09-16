export type Outcome =
  | "INTERESTED"
  | "CONVERTED"
  | "FOLLOW_UP_REQUESTED"
  | "NOT_INTERESTED"
  | "WRONG_NUMBER"
  | "DO_NOT_CONTACT"
  | "NO_RESPONSE";

export type Conversation = {
  id: string;
  user_id: string;
  campaign_id: string | null;
  lead_id: string | null;
  contact_name: string;
  from_number: string;
  to_number: string;
  timezone: string;
  status: "OPEN" | "CONCLUDED" | "UNRESOLVED";
  outcome: Outcome | null;
  message_template: string;
  campaign_objective: string;
  knowledge_context: string;
  agent_turn_count: number;
  max_agent_turns: number;
  opened_at: string;
  concluded_at: string | null;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
};

export type SmsMessage = {
  id: string;
  conversation_id: string;
  direction: "INBOUND" | "OUTBOUND";
  from_number: string;
  to_number: string;
  body: string;
  provider: string;
  provider_message_id: string | null;
  delivery_status: string;
  occurred_at: string;
};

export type ConversationDetail = Conversation & { messages: SmsMessage[] };

export type ConversationCreate = {
  campaign_id: string;
  lead_id: string;
  contact_name: string;
  from_number: string;
  to_number: string;
  timezone: string;
  message_template: string;
  campaign_objective: string;
  knowledge_context: string;
  consent_source: string;
  consented: boolean;
  max_agent_turns: number;
};

export type BulkLead = {
  lead_id: string;
  first_name: string;
  contact_name: string;
  phone_number: string;
  timezone: string;
  consented: boolean;
  consent_source: string;
};

export type BulkCampaignCreate = {
  campaign_id: string;
  from_number: string;
  message_template: string;
  campaign_objective: string;
  knowledge_context: string;
  max_agent_turns: number;
  start_immediately: boolean;
  leads: BulkLead[];
};

export type BulkCampaignResult = {
  created: string[];
  queued: string[];
  skipped: { lead_id: string; reason: string }[];
};
