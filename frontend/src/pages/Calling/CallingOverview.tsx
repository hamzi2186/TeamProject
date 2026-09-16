import { Clock3, PhoneCall, PhoneMissed, Radio } from "lucide-react";
import { Link } from "react-router-dom";
import { useCalls } from "../../api/calling";
import { CallTable } from "../../features/calling/CallTable";

export function CallingOverview() {
  const { data: calls = [], isLoading, error } = useCalls();
  const answered = calls.filter(call => ["COMPLETED", "IN_PROGRESS"].includes(call.status)).length;
  const noAnswer = calls.filter(call => call.status === "NO_ANSWER").length;
  const durations = calls.filter(call => call.duration_seconds != null).map(call => call.duration_seconds as number);
  const average = durations.length ? Math.round(durations.reduce((sum, value) => sum + value, 0) / durations.length) : 0;
  return <main className="page"><header className="page-header"><div><p className="eyebrow">Calling engine</p><h1>Conversation desk</h1><p className="subhead">A clear record of every lead conversation, from first ring to outcome.</p></div><Link className="primary-button" to="/calling/new"><PhoneCall size={17} />Start a call</Link></header><section className="metrics"><Metric icon={<Radio />} label="Calls made" value={calls.length} /><Metric icon={<PhoneCall />} label="Answered" value={answered} /><Metric icon={<PhoneMissed />} label="No answer" value={noAnswer} /><Metric icon={<Clock3 />} label="Avg duration" value={`${Math.floor(average / 60)}m ${String(average % 60).padStart(2, "0")}s`} /></section><section className="panel"><div className="panel-heading"><div><h2>Recent calls</h2><p>Latest activity across your calling campaigns.</p></div><span className="count">{calls.length} records</span></div>{isLoading ? <div className="loading">Loading call history...</div> : error ? <div className="error">{error.message}</div> : <CallTable calls={calls} />}</section></main>;
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: number | string }) { return <div className="metric"><span className="metric-icon">{icon}</span><div><span>{label}</span><strong>{value}</strong></div></div>; }