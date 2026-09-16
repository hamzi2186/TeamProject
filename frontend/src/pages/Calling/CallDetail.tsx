import { ArrowLeft, Clock3, FileText, Phone } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { useCall } from "../../api/calling";
import { CallBadge } from "../../features/calling/CallBadge";

export function CallDetail() {
  const { callId } = useParams();
  const { data: call, isLoading, error } = useCall(callId);
  if (isLoading) return <main className="page"><div className="loading">Loading conversation...</div></main>;
  if (error || !call) return <main className="page"><Link className="back-link" to="/calling"><ArrowLeft size={16} />Back to calls</Link><div className="error">{error?.message ?? "Call not found"}</div></main>;
  return <main className="page"><Link className="back-link" to="/calling"><ArrowLeft size={16} />Back to calls</Link><header className="detail-header"><div><p className="eyebrow">Call detail</p><h1>{call.lead_id}</h1><p className="subhead">{call.direction.toLowerCase()} conversation via {call.provider}</p></div><CallBadge value={call.status} /></header><div className="detail-grid"><section className="transcript panel"><div className="panel-heading"><div><h2><FileText size={18} />Transcript</h2><p>Conversation recording and extracted dialogue.</p></div></div>{call.transcript ? <p className="transcript-copy">{call.transcript}</p> : <div className="empty"><Phone size={20} /><span>No transcript available.</span></div>}</section><aside className="panel metadata"><h2>Call summary</h2><div className="summary">{call.summary || "No summary has been generated yet."}</div><dl><dt>Outcome</dt><dd><CallBadge value={call.outcome} /></dd><dt>Duration</dt><dd><Clock3 size={15} />{call.duration_seconds == null ? "-" : `${Math.floor(call.duration_seconds / 60)}m ${String(call.duration_seconds % 60).padStart(2, "0")}s`}</dd><dt>From</dt><dd>{call.from_number || "-"}</dd><dt>To</dt><dd>{call.to_number || "-"}</dd><dt>Provider call</dt><dd className="mono">{call.provider_call_id || "-"}</dd></dl></aside></div></main>;
}