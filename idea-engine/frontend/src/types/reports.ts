export type Channel = "CALL" | "SMS" | "EMAIL";
export type Direction = "INBOUND" | "OUTBOUND";

export type LeadOutcome =
  | "NEW"
  | "CONTACTING"
  | "INTERESTED"
  | "NOT_INTERESTED"
  | "FOLLOW_UP_REQUIRED"
  | "NO_ANSWER"
  | "NO_RESPONSE"
  | "CONVERTED"
  | "DO_NOT_CONTACT"
  | "COMPLETED"
  | "FAILED";

export type ReportStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";

export interface TimelineEvent {
  id: string;
  channel: Channel;
  direction: Direction;
  timestamp: string;
  sender?: string;
  recipient?: string;
  subject?: string;
  content: string;
  duration_seconds?: number;
  outcome?: string;
  delivery_status?: string;
}

export interface LeadReportItem {
  id: string;
  lead_id: string;
  lead_name: string;
  company_website?: string;
  phone?: string;
  email?: string;
  final_outcome: LeadOutcome;
  approach_summary: string;
  conversation_summary: string;
  outcome_reason: string;
  recommended_next_action?: string;
  first_activity_at?: string;
  last_activity_at?: string;
  source_event_count: number;
  channels_used: Channel[];
  campaigns: string[];
  timeline: TimelineEvent[];
}

export interface IdeaReportSummaryCounts {
  total_leads: number;
  interested: number;
  not_interested: number;
  follow_up_required: number;
  converted: number;
  no_answer: number;
  no_response: number;
  do_not_contact: number;
  failed: number;
  contacting: number;
  new: number;
}

export interface IdeaReportRun {
  id: string;
  report_date: string;
  status: ReportStatus;
  total_leads: number;
  summary_counts: IdeaReportSummaryCounts;
  generated_at?: string;
  document_filename?: string;
  download_url?: string;
  error?: string;
  created_at: string;
  updated_at: string;
  items?: LeadReportItem[];
}

export interface LeadJourneySummary {
  lead_id: string;
  lead_name: string;
  phone?: string;
  email?: string;
  website_url?: string;
  current_status: string;
  final_outcome: LeadOutcome;
  approach_summary: string;
  conversation_summary: string;
  outcome_reason: string;
  recommended_next_action?: string;
  channels_used: Channel[];
  campaigns: string[];
  timeline: TimelineEvent[];
}