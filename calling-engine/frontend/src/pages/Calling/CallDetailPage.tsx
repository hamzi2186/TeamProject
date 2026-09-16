import { useParams } from "react-router-dom";
import { CallDetail } from "../../features/calling/CallDetail";

export function CallDetailPage() {
  const { callId } = useParams<{ callId: string }>();

  if (!callId) {
    return (
      <div style={{ padding: 32, color: "var(--tx-lo)", fontSize: 14 }}>
        Invalid call ID.
      </div>
    );
  }

  return <CallDetail callId={callId} />;
}
