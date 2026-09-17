import {
  ArrowLeft,
  CheckCircle2,
  Circle,
  Database,
  Globe2,
  LoaderCircle,
  Mail,
  Phone,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ClientKbStage, ClientKbStatus, Lead, leadsApi } from "../api/leads";

const ACTIVE_STAGES = new Set<ClientKbStage>([
  "QUEUED",
  "CRAWLING",
  "EXTRACTING",
  "EMBEDDING",
]);

const STAGE_ORDER: ClientKbStage[] = [
  "QUEUED",
  "CRAWLING",
  "EXTRACTING",
  "EMBEDDING",
  "READY",
];

type StepState = "completed" | "active" | "pending" | "failed";

function stepState(stage: ClientKbStage, stepIndex: number): StepState {
  if (stage === "FAILED") return stepIndex === STAGE_ORDER.length - 1 ? "failed" : "pending";
  const current = stage === "PARTIAL" ? STAGE_ORDER.length - 1 : STAGE_ORDER.indexOf(stage);
  if (current < 0) return "pending";
  if (stepIndex < current) return "completed";
  if (stepIndex === current) return ACTIVE_STAGES.has(stage) ? "active" : "completed";
  return "pending";
}

function StepIcon({ state }: { state: StepState }) {
  if (state === "completed") return <CheckCircle2 size={18} />;
  if (state === "active") return <LoaderCircle className="kb-spinner" size={18} />;
  if (state === "failed") return <XCircle size={18} />;
  return <Circle size={18} />;
}

function statusLabel(stage: ClientKbStage) {
  if (stage === "PARTIAL") return "Partially completed";
  if (stage === "NOT_STARTED") return "Not started";
  return stage.charAt(0) + stage.slice(1).toLowerCase();
}

function ClientKnowledgeCard({
  status,
  loading,
  error,
  working,
  onBuild,
}: {
  status: ClientKbStatus | null;
  loading: boolean;
  error: string;
  working: boolean;
  onBuild: () => void;
}) {
  const stage = status?.processing_stage ?? "NOT_STARTED";
  const active = ACTIVE_STAGES.has(stage);
  const timeline = ["Job queued", "Crawling", "Extracting", "Embedding", "Ready"];
  const finalLabel = stage === "PARTIAL" ? "Partially completed" : stage === "FAILED" ? "Failed" : "Ready";
  const tone = stage === "FAILED" ? "failed" : stage === "PARTIAL" ? "warning" : active ? "crawling" : stage === "READY" ? "ready" : "neutral";
  const buttonLabel = active || working
    ? "Processing..."
    : stage === "READY" || stage === "PARTIAL"
      ? "Rebuild Knowledge Base"
      : stage === "FAILED"
        ? "Retry Knowledge Base"
        : "Build Knowledge Base";

  return (
    <section className="detail-card kb-card">
      <div className="kb-card-header">
        <div>
          <p className="eyebrow dark">Client knowledge</p>
          <h2><Database size={19} />Processing status</h2>
        </div>
        <span className={`pill ${tone}`}>{loading ? "Loading" : statusLabel(stage)}</span>
      </div>

      <dl className="kb-summary">
        <dt>Website</dt><dd>{status?.website_url || "No website supplied"}</dd>
        <dt>KB status</dt><dd>{status?.knowledge_base_status || "NOT_CREATED"}</dd>
        <dt>Current stage</dt><dd>{statusLabel(stage)}</dd>
      </dl>

      <div className="kb-timeline" aria-label="Knowledge base processing stages">
        <div className={`kb-step ${status?.website_id ? "completed" : "pending"}`}>
          <StepIcon state={status?.website_id ? "completed" : "pending"} />
          <span>Website linked</span>
        </div>
        {timeline.map((label, index) => {
          const state = stepState(stage, index);
          return (
            <div className={`kb-step ${state}`} key={label}>
              <StepIcon state={state} />
              <span>{index === timeline.length - 1 ? finalLabel : label}</span>
            </div>
          );
        })}
      </div>

      {status && (
        <div className="kb-metrics">
          <div><span>Discovered</span><strong>{status.pages_discovered}</strong></div>
          <div><span>Processed</span><strong>{status.pages_processed}</strong></div>
          <div><span>Succeeded</span><strong>{status.pages_succeeded}</strong></div>
          {status.pages_failed != null && <div><span>Failed pages</span><strong>{status.pages_failed}</strong></div>}
          <div><span>Chunks</span><strong>{status.chunks_created}</strong></div>
          {status.embeddings_created != null && <div><span>Embeddings</span><strong>{status.embeddings_created}</strong></div>}
        </div>
      )}

      {(status?.error_message || error) && (
        <div className={stage === "PARTIAL" ? "notice warning" : "notice error"} role="alert">
          {status?.error_message || error}
        </div>
      )}

      {status?.has_website ? (
        <button className="secondary kb-action" disabled={active || working} onClick={onBuild}>
          {active || working ? <LoaderCircle className="kb-spinner" size={16} /> : <RefreshCw size={16} />}
          {buttonLabel}
        </button>
      ) : (
        <p className="kb-no-site">Add a website to this lead before building a Client KB.</p>
      )}
    </section>
  );
}

export function LeadDetailPage() {
  const { leadId = "" } = useParams();
  const [lead, setLead] = useState<Lead | null>(null);
  const [kbStatus, setKbStatus] = useState<ClientKbStatus | null>(null);
  const [error, setError] = useState("");
  const [kbError, setKbError] = useState("");
  const [kbLoading, setKbLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [pollVersion, setPollVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;
    leadsApi.detail(leadId)
      .then((value) => { if (!cancelled) setLead(value); })
      .catch((caught: unknown) => {
        if (!cancelled) setError(caught instanceof Error ? caught.message : "Could not load lead.");
      });
    return () => { cancelled = true; };
  }, [leadId]);

  useEffect(() => {
    if (!lead) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      try {
        const next = await leadsApi.knowledgeBaseStatus(leadId);
        if (cancelled) return;
        setKbStatus(next);
        setKbError("");
        setKbLoading(false);
        if (ACTIVE_STAGES.has(next.processing_stage)) timer = setTimeout(poll, 2500);
      } catch (caught: unknown) {
        if (cancelled) return;
        setKbLoading(false);
        setKbError(caught instanceof Error ? caught.message : "Could not load Client KB status.");
      }
    };

    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [lead, leadId, pollVersion]);

  const buildOrRefresh = async () => {
    if (!lead || working) return;
    setWorking(true);
    setKbError("");
    try {
      const next = kbStatus?.website_id
        ? await leadsApi.refreshKnowledgeBase(lead.id)
        : await leadsApi.buildKnowledgeBase(lead.id, lead.website_url);
      setKbStatus(next);
      if (next.website_id && !lead.website_id) setLead({ ...lead, website_id: next.website_id });
      setPollVersion((value) => value + 1);
    } catch (caught: unknown) {
      setKbError(caught instanceof Error ? caught.message : "Could not start Client KB processing.");
    } finally {
      setWorking(false);
    }
  };

  if (error) return <section className="page"><div className="notice error">{error}</div></section>;
  if (!lead) return <section className="page"><div className="loading-card">Loading lead…</div></section>;

  return (
    <section className="page">
      <Link className="back-link" to="/leads"><ArrowLeft size={16} />Back to leads</Link>
      <div className="detail-hero">
        <div>
          <p className="eyebrow dark">Lead detail</p>
          <h1>{lead.display_name || "Unnamed lead"}</h1>
          <div className="contact-line">
            <span><Mail size={16} />{lead.email || "No email"}</span>
            <span><Phone size={16} />{lead.phone || "No phone"}</span>
            <span><Globe2 size={16} />{lead.website_url || "No website"}</span>
          </div>
        </div>
        <span className="pill ready">{lead.current_status}</span>
      </div>
      <div className="detail-grid">
        <div className="detail-card">
          <h2>Overview</h2>
          <dl>
            <dt>HubSpot source ID</dt><dd>{lead.hubspot_contact_id}</dd>
            <dt>Last updated</dt><dd>{new Date(lead.updated_at).toLocaleString()}</dd>
          </dl>
        </div>
        <div className="detail-card">
          <h2>Channel readiness</h2>
          <p>{lead.phone ? "Calling and SMS ready" : "Calling and SMS unavailable: missing phone"}</p>
          <p>{lead.email ? "Email ready" : "Email unavailable: missing address"}</p>
          <p>{lead.website_url ? "Website supplied" : "Client KB unavailable: missing website"}</p>
        </div>
        <ClientKnowledgeCard
          status={kbStatus}
          loading={kbLoading}
          error={kbError}
          working={working}
          onBuild={buildOrRefresh}
        />
      </div>
    </section>
  );
}
