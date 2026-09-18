import {
  AlertCircle,
  CheckCircle2,
  Download,
  ExternalLink,
  LogOut,
  RefreshCw,
  Search,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { HubSpotContact, HubSpotStatus, ImportResult, hubspotApi } from "../api/hubspot";

function readiness(contact: HubSpotContact) {
  const missing = [!contact.phone && "phone", !contact.email && "email", !contact.website && "website"].filter(Boolean);
  return missing.length ? `Missing ${missing.join(", ")}` : "Ready";
}

export function HubSpotPage() {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<HubSpotStatus | null>(null);
  const [contacts, setContacts] = useState<HubSpotContact[]>([]);
  const [nextAfter, setNextAfter] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [selectAll, setSelectAll] = useState(false);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ImportResult | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const callbackOutcome = searchParams.get("hubspot");
  const callbackReason = searchParams.get("reason");
  const websiteIngestionFailureCount = new Set(
    result?.website_ingestion_failures.flatMap((failure) => failure.hubspot_contact_ids) ?? [],
  ).size;
  const callbackError = callbackReason === "configuration"
    ? "HubSpot could not complete authorization. Verify HUBSPOT_REDIRECT_URI exactly matches the redirect URI registered in HubSpot and that its callback host is browser-reachable."
    : callbackReason === "state"
      ? "HubSpot authorization expired or was already used. Start the connection again."
      : callbackReason === "denied"
        ? "HubSpot authorization was denied."
        : "HubSpot authorization could not be completed. Start the connection again.";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const current = await hubspotApi.status();
      setStatus(current);
      if (current.connected) {
        const page = await hubspotApi.contacts();
        setContacts(page.contacts);
        setNextAfter(page.next_after);
      } else {
        setContacts([]);
        setNextAfter(null);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load HubSpot status.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleOAuthConnect() {
    setWorking(true);
    setError("");
    try {
      const response = await hubspotApi.connect();
      window.location.assign(response.authorization_url);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not initiate HubSpot OAuth.");
      setWorking(false);
    }
  }

  async function handleDisconnect() {
    if (!window.confirm("Are you sure you want to disconnect this HubSpot account?")) {
      return;
    }
    setWorking(true);
    setError("");
    try {
      const newStatus = await hubspotApi.disconnect();
      setStatus(newStatus);
      setContacts([]);
      setSelected(new Set());
      setSelectAll(false);
      setNextAfter(null);
      setResult(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not disconnect HubSpot.");
    } finally {
      setWorking(false);
    }
  }

  async function importContacts() {
    setWorking(true);
    setError("");
    setResult(null);
    try {
      const imported = await hubspotApi.importContacts([...selected], selectAll);
      setResult(imported);
      setSelected(new Set());
      setSelectAll(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Import failed.");
    } finally {
      setWorking(false);
    }
  }

  async function nextPage() {
    if (!nextAfter) return;
    setWorking(true);
    try {
      const page = await hubspotApi.contacts(nextAfter);
      setContacts(page.contacts);
      setNextAfter(page.next_after);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load contacts.");
    } finally {
      setWorking(false);
    }
  }

  const filteredContacts = contacts.filter((c) => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    const name = [c.firstname, c.lastname].filter(Boolean).join(" ").toLowerCase();
    const email = (c.email || "").toLowerCase();
    const phone = (c.phone || "").toLowerCase();
    return name.includes(term) || email.includes(term) || phone.includes(term);
  });

  if (loading) {
    return (
      <section className="page">
        <div className="loading-card">
          <RefreshCw className="spin" size={24} style={{ margin: "0 auto 12px auto" }} />
          <p>Loading HubSpot integration status…</p>
        </div>
      </section>
    );
  }

  return (
    <section className="page" style={{ maxWidth: 1100, margin: "0 auto" }}>
      <header className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <p className="eyebrow dark">Integrations</p>
          <h1 style={{ display: "flex", alignItems: "center", gap: 10, margin: "4px 0" }}>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 34,
                height: 34,
                background: "#ff7a59",
                color: "#fff",
                borderRadius: 8,
                fontSize: 18,
                fontWeight: 800,
              }}
            >
              H
            </span>
            HubSpot CRM
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: 14 }}>
            Connect your HubSpot CRM account directly to view contacts and import them as T Rex leads.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="secondary" onClick={load} disabled={working}>
            <RefreshCw size={15} /> Refresh
          </button>
          {status?.connected && (
            <button
              className="secondary"
              onClick={handleDisconnect}
              disabled={working}
              style={{ color: "#ef4444", borderColor: "rgba(239, 68, 68, 0.3)" }}
            >
              <LogOut size={15} /> Disconnect
            </button>
          )}
        </div>
      </header>

      {error && (
        <div className="notice error" role="alert" style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}
      {callbackOutcome === "connected" && <div className="notice success" role="status">HubSpot connected successfully.</div>}
      {callbackOutcome === "error" && <div className="notice error" role="alert">{callbackError}</div>}
      {!status?.connected ? (
        <div
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-lg)",
            padding: "32px 28px",
            boxShadow: "var(--shadow-md)",
          }}
        >
          <h2 style={{ fontSize: 20, fontWeight: 700, margin: "0 0 8px", color: "var(--text-primary)" }}>
            Connect HubSpot
          </h2>
          <p style={{ margin: "0 0 20px", fontSize: 14, color: "var(--text-secondary)" }}>
            Sign in to HubSpot and authorize T Rex to securely access your CRM contacts.
          </p>
          <button
            type="button"
            className="primary"
            onClick={handleOAuthConnect}
            disabled={working}
            style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
          >
            {working ? <RefreshCw className="spin" size={16} /> : <ExternalLink size={16} />}
            {working ? "Connecting..." : "Connect HubSpot"}
          </button>
        </div>
      ) : (
        <>
          {/* Connected Status Card */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "18px 24px",
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              marginBottom: 20,
              backdropFilter: "blur(16px)",
              flexWrap: "wrap",
              gap: 16,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <span className="status-dot" style={{ width: 10, height: 10 }} />
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <strong style={{ fontSize: 16, color: "var(--text-primary)" }}>Connected to HubSpot</strong>
                  <span className="pill ready" style={{ fontSize: 11 }}>Active</span>
                </div>
                <p style={{ margin: "4px 0 0 0", fontSize: 13, color: "var(--text-secondary)" }}>
                  Portal ID: <strong style={{ color: "#fff" }}>{status.portal_id || "Standard"}</strong> · Scopes:{" "}
                  {status.scopes?.length ? status.scopes.join(", ") : "contacts.read, contacts.write"}
                </p>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <CheckCircle2 size={24} style={{ color: "var(--green)" }} />
              <button
                className="secondary compact"
                onClick={handleDisconnect}
                disabled={working}
                style={{ color: "#ef4444", borderColor: "rgba(239, 68, 68, 0.3)" }}
              >
                <LogOut size={14} /> Disconnect
              </button>
            </div>
          </div>

          {result && (
            <div className="notice success" style={{ marginBottom: 20 }}>
              Imported {result.imported} contacts: {result.created} created, {result.updated} updated in T Rex leads.
            </div>
          )}
          {websiteIngestionFailureCount > 0 && (
            <div className="notice error" role="alert" style={{ marginBottom: 20 }}>
              Imported the leads, but could not start website ingestion for {websiteIngestionFailureCount} contact{websiteIngestionFailureCount === 1 ? "" : "s"}. Re-import them or use Build Knowledge Base to retry.
            </div>
          )}

          {/* Contact Table Card */}
          <div className="table-card">
            <div
              className="table-toolbar"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "14px 20px",
                borderBottom: "1px solid var(--border)",
                gap: 16,
                flexWrap: "wrap",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                <label className="check-label" style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13 }}>
                  <input
                    type="checkbox"
                    checked={selectAll}
                    onChange={(event) => {
                      setSelectAll(event.target.checked);
                      setSelected(new Set());
                    }}
                  />
                  <span>Select all HubSpot contacts</span>
                </label>
                {selected.size > 0 && !selectAll && (
                  <span style={{ fontSize: 12, color: "var(--accent)" }}>{selected.size} selected</span>
                )}
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                {/* Search contacts filter */}
                <div style={{ position: "relative", width: 220 }}>
                  <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
                  <input
                    type="text"
                    className="input"
                    placeholder="Search contacts…"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    style={{ paddingLeft: 30, height: 34, fontSize: 12 }}
                  />
                </div>

                <button
                  className="primary compact"
                  disabled={working || (!selectAll && selected.size === 0)}
                  onClick={importContacts}
                  style={{ display: "flex", alignItems: "center", gap: 6 }}
                >
                  <Download size={14} />
                  Import {selectAll ? "All" : selected.size > 0 ? `Selected (${selected.size})` : ""}
                </button>
              </div>
            </div>

            {filteredContacts.length === 0 ? (
              <div className="table-empty" style={{ padding: 40, textAlign: "center", color: "var(--text-muted)" }}>
                {contacts.length === 0 ? "No HubSpot contacts found in this portal." : "No contacts match your search."}
              </div>
            ) : (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th style={{ width: 40 }} />
                      <th>Lead Name</th>
                      <th>Phone</th>
                      <th>Email</th>
                      <th>Website</th>
                      <th>Readiness</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredContacts.map((contact) => {
                      const id = contact.provider_contact_id;
                      return (
                        <tr key={id}>
                          <td>
                            <input
                              type="checkbox"
                              disabled={selectAll}
                              checked={selected.has(id)}
                              onChange={() =>
                                setSelected((current) => {
                                  const next = new Set(current);
                                  next.has(id) ? next.delete(id) : next.add(id);
                                  return next;
                                })
                              }
                            />
                          </td>
                          <td>
                            <strong>
                              {[contact.firstname, contact.lastname].filter(Boolean).join(" ") || "Unnamed contact"}
                            </strong>
                          </td>
                          <td style={{ fontFamily: "monospace", fontSize: 12.5 }}>{contact.phone || "—"}</td>
                          <td>{contact.email || "—"}</td>
                          <td>{contact.website || "—"}</td>
                          <td>
                            <span className={readiness(contact) === "Ready" ? "pill ready" : "pill warning"}>
                              {readiness(contact)}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {nextAfter && (
              <div className="pagination" style={{ padding: "12px 20px", borderTop: "1px solid var(--border)", display: "flex", justifyContent: "flex-end" }}>
                <button className="secondary compact" disabled={working} onClick={nextPage}>
                  Next page
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}
