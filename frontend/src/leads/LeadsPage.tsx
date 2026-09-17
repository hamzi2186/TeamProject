import { CheckCircle2, PhoneCall, RefreshCw, Users } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { callingApi } from "../api/calling";
import { Lead, leadsApi } from "../api/leads";
import { LiveCallModal } from "../features/calling/LiveCallModal";

export function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [successNotice, setSuccessNotice] = useState("");
  const [callingLeadId, setCallingLeadId] = useState<string | null>(null);
  const [activeCall, setActiveCall] = useState<{
    callId: string;
    leadName: string;
    phoneNumber: string;
    companyName?: string;
  } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setLeads(await leadsApi.list());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load leads.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function callLead(lead: Lead, isMock: boolean = false) {
    const phone = lead.phone || "+10000000000";
    if (!lead.phone && !isMock) return;
    setCallingLeadId(lead.id);
    setError("");
    setSuccessNotice("");

    try {
      const apiMethod = isMock ? callingApi.startMockCall : callingApi.startCall;
      const res = await apiMethod({
        lead_id: lead.id,
        phone_number: phone,
        purpose: "Follow up with lead",
        is_mock: isMock,
        lead_variables: {
          name: lead.display_name || (`${lead.first_name || ""} ${lead.last_name || ""}`.trim() || "Lead"),
          email: lead.email || "",
        },
      });

      const leadDisplayName = lead.display_name || (`${lead.first_name || ""} ${lead.last_name || ""}`.trim() || "Lead Contact");
      setActiveCall({
        callId: res.data.call_id,
        leadName: leadDisplayName,
        phoneNumber: phone,
        companyName: lead.website_url || undefined,
      });

      setSuccessNotice(isMock ? `Simulated Mock AI voice call started with ${leadDisplayName}.` : `Active AI voice call initiated with ${leadDisplayName}.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not start call.");
    } finally {
      setCallingLeadId(null);
    }
  }

  return (
    <section className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow dark">Canonical Directory</p>
          <h1>Leads Workspace</h1>
          <p>Imported HubSpot contacts prepared for autonomous research, outreach, and AI calling.</p>
        </div>
        <div className="header-actions">
          <Link className="primary compact" to="/hubspot">
            Import from HubSpot
          </Link>
          <button className="secondary compact" onClick={load}>
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>
      </header>

      {error && <div className="notice error">{error}</div>}
      {successNotice && (
        <div className="notice success">
          <CheckCircle2 size={16} />
          <span>{successNotice}</span>
          <Link to="/calling" style={{ marginLeft: "auto", textDecoration: "underline", fontWeight: 600 }}>
            Open Calling Engine &rarr;
          </Link>
        </div>
      )}

      {loading ? (
        <div className="loading-card">Loading leads…</div>
      ) : leads.length === 0 ? (
        <div className="empty-card">
          <Users size={36} />
          <h2>No leads imported yet</h2>
          <p>Connect your HubSpot CRM or run an import to populate the canonical lead database.</p>
          <Link className="primary action" to="/hubspot">
            Open HubSpot Sync
          </Link>
        </div>
      ) : (
        <div className="table-card">
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Lead Name</th>
                  <th>Company / Website</th>
                  <th>Phone Number</th>
                  <th>Email</th>
                  <th>KB Status</th>
                  <th>Lead Status</th>
                  <th>Outbound Call</th>
                </tr>
              </thead>
              <tbody>
                {leads.map((lead) => (
                  <tr key={lead.id}>
                    <td>
                      <Link to={`/leads/${lead.id}`}>
                        <strong>{lead.display_name || "Unnamed lead"}</strong>
                      </Link>
                    </td>
                    <td>{lead.website_url || "—"}</td>
                    <td>{lead.phone ? <code>{lead.phone}</code> : <span className="text-muted">No phone</span>}</td>
                    <td>{lead.email || "—"}</td>
                    <td>
                      <span className="pill neutral" title="Mock search enabled pending crawler integration">
                        Mock KB ready
                      </span>
                    </td>
                    <td>
                      <span className="pill ready">{lead.current_status}</span>
                    </td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      <div style={{ display: "flex", gap: "6px" }}>
                        <button
                          className="primary compact"
                          disabled={!lead.phone || callingLeadId === lead.id}
                          onClick={() => void callLead(lead, false)}
                          title={lead.phone ? "Initiate AI voice call" : "Phone number required"}
                        >
                          <PhoneCall size={14} />
                          {callingLeadId === lead.id ? "Calling…" : lead.phone ? "Call lead" : "No phone"}
                        </button>
                        <button
                          className="secondary compact"
                          disabled={callingLeadId === lead.id}
                          onClick={() => void callLead(lead, true)}
                          title="Simulate interactive AI voice call (No credits required)"
                          style={{ borderColor: "#10b981", color: "#10b981", padding: "6px 10px", fontSize: "0.8rem", fontWeight: 600 }}
                        >
                          Mock Call
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeCall && (
        <LiveCallModal
          callId={activeCall.callId}
          leadName={activeCall.leadName}
          phoneNumber={activeCall.phoneNumber}
          companyName={activeCall.companyName}
          onClose={() => {
            setActiveCall(null);
            void load();
          }}
        />
      )}
    </section>
  );
}
