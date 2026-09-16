import { useParams } from "react-router-dom";
import { CallDetail } from "../../features/calling/CallDetail";

export function CallDetailPage() {
  const { callId } = useParams<{ callId: string }>();

  if (!callId) {
    return <div className="page"><p>Invalid call ID.</p></div>;
  }

  return (
    <div className="page">
      <CallDetail callId={callId} />
    </div>
  );
}
