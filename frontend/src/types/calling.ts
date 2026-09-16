export type CallDirection = "OUTBOUND" | "INBOUND";

export type CallStatus =
  | "QUEUED"
  | "RINGING"
  | "IN_PROGRESS"
  | "COMPLETED"
  | "NO_ANSWER"
  | "FAILED"
  | "CANCELLED";

export type CallOutcome =
  | "INTERESTED"
  | "NOT_INTERESTED"
  | "FOLLOW_UP_REQUIRED"
  | "NO_ANSWER"
  | "CONVERTED"
  | "DO_NOT_CONTACT"
  | "COMPLETED"
  | "FAILED"
  | null;

export interface Call {
  call_id: string;
  conversation_id: string | null;
  user_id: string;
  lead_id: string;
  direction: CallDirection;
  from_number: string | null;
  to_number: string | null;
  provider: string;
  provider_call_id: string | null;
  status: CallStatus;
  started_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  transcript: string | null;
  summary: string | null;
  outcome: CallOutcome;
  recording_url: string | null;
  provider_payload: Record<string, unknown>;
}

export interface CallsResponse {
  success: boolean;
  data: Call[];
  error: string | null;
}

export interface CallResponse {
  success: boolean;
  data: Call;
  error: string | null;
}