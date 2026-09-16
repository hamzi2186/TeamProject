import { RefreshCw, Users } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Lead, leadsApi } from "../api/leads";

export function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setLeads(await leadsApi.list()); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not load leads."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  return <section className="page"><header className="page-header"><div><p className="eyebrow dark">Workspace</p><h1>Leads</h1><p>Canonical contacts ready for research and outreach.</p></div><button className="secondary" onClick={load}><RefreshCw size={16} />Refresh</button></header>{error && <div className="notice error">{error}</div>}{loading ? <div className="loading-card">Loading leads…</div> : leads.length === 0 ? <div className="empty-card"><Users size={30} /><h2>No leads yet</h2><p>Import contacts from HubSpot to build your lead workspace.</p><Link className="primary action" to="/hubspot">Open HubSpot</Link></div> : <div className="table-card"><div className="table-scroll"><table><thead><tr><th>Lead</th><th>Company / website</th><th>Phone</th><th>Email</th><th>KB status</th><th>Lead status</th><th>Last activity</th></tr></thead><tbody>{leads.map((lead) => <tr key={lead.id}><td><Link to={`/leads/${lead.id}`}>{lead.display_name || "Unnamed lead"}</Link></td><td>{lead.website_url || "—"}</td><td>{lead.phone || "—"}</td><td>{lead.email || "—"}</td><td><span className="pill neutral">Not started</span></td><td><span className="pill ready">{lead.current_status}</span></td><td>{new Date(lead.updated_at).toLocaleDateString()}</td></tr>)}</tbody></table></div></div>}</section>;
}
