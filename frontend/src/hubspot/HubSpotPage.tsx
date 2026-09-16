import { CheckCircle2, Download, ExternalLink, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { HubSpotContact, HubSpotStatus, ImportResult, hubspotApi } from "../api/hubspot";

function readiness(contact: HubSpotContact) {
  const missing = [!contact.phone && "phone", !contact.email && "email", !contact.website && "website"].filter(Boolean);
  return missing.length ? `Missing ${missing.join(", ")}` : "Ready";
}

export function HubSpotPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [status, setStatus] = useState<HubSpotStatus | null>(null);
  const [contacts, setContacts] = useState<HubSpotContact[]>([]);
  const [nextAfter, setNextAfter] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [selectAll, setSelectAll] = useState(false);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ImportResult | null>(null);
  const [connectionMessage, setConnectionMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const current = await hubspotApi.status();
      setStatus(current);
      if (current.connected) {
        const page = await hubspotApi.contacts();
        setContacts(page.contacts); setNextAfter(page.next_after);
      }
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not load HubSpot."); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    const connected = new URLSearchParams(location.search).get("connected");
    if (connected === "success") {
      setConnectionMessage("HubSpot connected successfully.");
    } else if (connected === "error") {
      setConnectionMessage("HubSpot connection could not be completed. Please try again.");
    } else {
      return;
    }
    navigate(location.pathname, { replace: true });
  }, [location.pathname, location.search, navigate]);

  async function connect() {
    setWorking(true); setError("");
    try { const response = await hubspotApi.connect(); window.location.assign(response.authorization_url); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not connect HubSpot."); setWorking(false); }
  }

  async function importContacts() {
    setWorking(true); setError(""); setResult(null);
    try {
      const imported = await hubspotApi.importContacts([...selected], selectAll);
      setResult(imported); setSelected(new Set()); setSelectAll(false);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Import failed."); }
    finally { setWorking(false); }
  }

  async function nextPage() {
    if (!nextAfter) return;
    setWorking(true);
    try { const page = await hubspotApi.contacts(nextAfter); setContacts(page.contacts); setNextAfter(page.next_after); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not load contacts."); }
    finally { setWorking(false); }
  }

  if (loading) return <section className="page"><div className="loading-card">Loading HubSpot connection…</div></section>;
  return (
    <section className="page">
      <header className="page-header"><div><p className="eyebrow dark">Integrations</p><h1>HubSpot</h1><p>Connect your CRM and turn contacts into canonical T Rex leads.</p></div><button className="secondary" onClick={load}><RefreshCw size={16} />Refresh</button></header>
      {connectionMessage && <div className="notice success" role="status">{connectionMessage}</div>}
      {error && <div className="notice error" role="alert">{error}</div>}
      {!status?.connected ? (
        <div className="empty-card"><div className="integration-icon">H</div><h2>HubSpot is not connected</h2><p>Connect your CRM to import leads into T Rex.</p><button className="primary action" disabled={working} onClick={connect}>Connect HubSpot<ExternalLink size={16} /></button></div>
      ) : (
        <>
          <div className="status-card"><div><span className="status-dot" /><strong>Connected</strong><p>Portal {status.portal_id} · Updated {status.updated_at ? new Date(status.updated_at).toLocaleString() : "just now"}</p></div><CheckCircle2 size={24} /></div>
          {result && <div className="notice success">Imported {result.imported}: {result.created} created, {result.updated} updated.</div>}
          <div className="table-card">
            <div className="table-toolbar"><label className="check-label"><input type="checkbox" checked={selectAll} onChange={(event) => { setSelectAll(event.target.checked); setSelected(new Set()); }} />Select all HubSpot contacts</label><button className="primary compact" disabled={working || (!selectAll && selected.size === 0)} onClick={importContacts}><Download size={16} />Import {selectAll ? "all" : `selected (${selected.size})`}</button></div>
            {contacts.length === 0 ? <div className="table-empty">No HubSpot contacts found.</div> : <div className="table-scroll"><table><thead><tr><th /><th>Lead</th><th>Phone</th><th>Email</th><th>Website</th><th>Readiness</th></tr></thead><tbody>{contacts.map((contact) => { const id = contact.provider_contact_id; return <tr key={id}><td><input type="checkbox" disabled={selectAll} checked={selected.has(id)} onChange={() => setSelected((current) => { const next = new Set(current); next.has(id) ? next.delete(id) : next.add(id); return next; })} /></td><td><strong>{[contact.firstname, contact.lastname].filter(Boolean).join(" ") || "Unnamed contact"}</strong></td><td>{contact.phone || "—"}</td><td>{contact.email || "—"}</td><td>{contact.website || "—"}</td><td><span className={readiness(contact) === "Ready" ? "pill ready" : "pill warning"}>{readiness(contact)}</span></td></tr>; })}</tbody></table></div>}
            {nextAfter && <div className="pagination"><button className="secondary" disabled={working} onClick={nextPage}>Next page</button></div>}
          </div>
        </>
      )}
    </section>
  );
}
