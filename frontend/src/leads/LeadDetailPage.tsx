import { ArrowLeft, Globe2, Mail, Phone } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Lead, leadsApi } from "../api/leads";

export function LeadDetailPage() {
  const { leadId = "" } = useParams();
  const [lead, setLead] = useState<Lead | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { leadsApi.detail(leadId).then(setLead).catch((caught) => setError(caught instanceof Error ? caught.message : "Could not load lead.")); }, [leadId]);
  if (error) return <section className="page"><div className="notice error">{error}</div></section>;
  if (!lead) return <section className="page"><div className="loading-card">Loading lead…</div></section>;
  return <section className="page"><Link className="back-link" to="/leads"><ArrowLeft size={16} />Back to leads</Link><div className="detail-hero"><div><p className="eyebrow dark">Lead detail</p><h1>{lead.display_name || "Unnamed lead"}</h1><div className="contact-line"><span><Mail size={16} />{lead.email || "No email"}</span><span><Phone size={16} />{lead.phone || "No phone"}</span><span><Globe2 size={16} />{lead.website_url || "No website"}</span></div></div><span className="pill ready">{lead.current_status}</span></div><div className="detail-grid"><div className="detail-card"><h2>Overview</h2><dl><dt>HubSpot source ID</dt><dd>{lead.hubspot_contact_id}</dd><dt>Knowledge base</dt><dd>{lead.website_id ? "Linked" : "Unavailable until website ingestion"}</dd><dt>Last updated</dt><dd>{new Date(lead.updated_at).toLocaleString()}</dd></dl></div><div className="detail-card"><h2>Channel readiness</h2><p>{lead.phone ? "Calling and SMS ready" : "Calling and SMS unavailable: missing phone"}</p><p>{lead.email ? "Email ready" : "Email unavailable: missing address"}</p><p>{lead.website_url ? "Website supplied" : "Client KB unavailable: missing website"}</p></div></div></section>;
}
