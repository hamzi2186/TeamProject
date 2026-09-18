import { useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, ArrowLeft, Bot, MessageSquareText, Plus, Send, ShieldCheck, Signal, Users } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { smsApi } from "../../api/sms";
import { useConversationSocket } from "../../hooks/useConversationSocket";
import type { BulkCampaignCreate, Conversation, ConversationCreate } from "../../types/sms";
import { BulkCampaignForm } from "./BulkCampaignForm";
import { NewConversationForm } from "./NewConversationForm";

const formatter = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
const isMockTransport = import.meta.env.VITE_SMS_PROVIDER === "mock";
const smsTransport = isMockTransport ? "Mock SMS transport" : "Twilio transport";

export function SmsWorkspace() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [showNew, setShowNew] = useState(false);
  const [showBulk, setShowBulk] = useState(false);
  const [replyBody, setReplyBody] = useState("");
  const conversations = useQuery({ queryKey: ["conversations"], queryFn: smsApi.list, refetchInterval: 3000 });
  const detail = useQuery({ queryKey: ["conversation", conversationId], queryFn: () => smsApi.detail(conversationId!), enabled: Boolean(conversationId) });
  const connected = useConversationSocket(conversationId);
  const create = useMutation({
    mutationFn: smsApi.create,
    onSuccess: (value) => {
      void client.invalidateQueries({ queryKey: ["conversations"] });
      setShowNew(false);
      navigate(`/sms/${value.id}`);
    },
  });
  const bulkLaunch = useMutation({
    mutationFn: smsApi.bulkLaunch,
    onSuccess: () => void client.invalidateQueries({ queryKey: ["conversations"] }),
  });
  const start = useMutation({
    mutationFn: () => smsApi.start(conversationId!),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["conversation", conversationId] }),
  });
  const mockReply = useMutation({
    mutationFn: (body: string) => smsApi.mockReply(conversationId!, body),
    onSuccess: () => {
      setReplyBody("");
      void client.invalidateQueries({ queryKey: ["conversation", conversationId] });
    },
  });
  const rows = conversations.data ?? [];
  const openCount = rows.filter((item) => item.status === "OPEN").length;
  const interested = rows.filter((item) => item.outcome === "INTERESTED" || item.outcome === "CONVERTED").length;

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">Skip to conversation</a>
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark">T</div><div><strong>T Rex</strong><span>SMS Engine</span></div></div>
        <nav aria-label="SMS navigation">
          <a className="nav-item" href="/"><ArrowLeft size={18} /> T Rex Platform</a>
          <Link className="nav-item active" to="/sms"><MessageSquareText size={18} /> Conversations</Link>
        </nav>
        <div className="sidebar-status"><Signal size={16} /><div><strong>Engine online</strong><span>{smsTransport}</span></div></div>
      </aside>
      <div className="workspace">
        <header className="topbar"><div><p className="eyebrow">Autonomous outreach</p><h1>SMS conversations</h1></div><div className="topbar-actions"><button className="button secondary" onClick={() => setShowBulk(true)}><Users size={18} /> Bulk campaign</button><button className="button primary" onClick={() => setShowNew(true)}><Plus size={18} /> New conversation</button></div></header>
        <section className="metrics" aria-label="SMS overview">
          <Metric icon={<Activity size={18} />} label="Active" value={openCount} />
          <Metric icon={<MessageSquareText size={18} />} label="Total threads" value={rows.length} />
          <Metric icon={<ShieldCheck size={18} />} label="Positive outcomes" value={interested} />
        </section>
        <main id="main" className="conversation-layout">
          <section className={`thread-list ${conversationId ? "mobile-hidden" : ""}`} aria-label="Conversation list">
            <header><h2>Inbox</h2><span>{rows.length}</span></header>
            {conversations.isLoading && <div className="empty-state">Loading conversations…</div>}
            {conversations.isError && <div className="empty-state error">Could not load conversations.</div>}
            {!conversations.isLoading && rows.length === 0 && <div className="empty-state"><MessageSquareText size={28} /><strong>No conversations yet</strong><span>Create a fixture conversation to test the engine.</span></div>}
            {rows.map((conversation) => <ConversationRow key={conversation.id} conversation={conversation} active={conversation.id === conversationId} />)}
          </section>
          <section className={`thread-detail ${!conversationId ? "mobile-hidden" : ""}`}>
            {!conversationId && <div className="empty-detail"><Bot size={36} /><h2>Select a conversation</h2><p>Messages and live delivery updates will appear here.</p></div>}
            {detail.data && <>
              <header className="detail-header"><Link to="/sms" className="icon-button back-button" aria-label="Back to conversations"><ArrowLeft size={20} /></Link><div className="avatar">{initials(detail.data.contact_name)}</div><div className="contact"><h2>{detail.data.contact_name}</h2><span>{detail.data.to_number} · {detail.data.timezone}</span></div><div className={`live-state ${connected ? "connected" : ""}`}><span />{connected ? "Live" : "Reconnecting"}</div></header>
              <div className="context-strip"><span className={`status status-${detail.data.status.toLowerCase()}`}>{detail.data.status}</span><span>{detail.data.outcome ? detail.data.outcome.replaceAll("_", " ") : "No outcome yet"}</span><span>{detail.data.agent_turn_count}/{detail.data.max_agent_turns} agent turns</span></div>
              <div className="messages" aria-live="polite">
                {detail.data.messages.length === 0 && <div className="empty-messages"><Bot size={28} /><strong>Ready to start</strong><p>The opening message will combine the campaign template with approved KB context.</p></div>}
                {detail.data.messages.map((message) => <article key={message.id} className={`message ${message.direction.toLowerCase()}`}><div className="bubble"><p>{message.body}</p><footer><time>{formatter.format(new Date(message.occurred_at))}</time><span>{message.delivery_status.toLowerCase()}</span></footer></div></article>)}
              </div>
              <footer className={`composer ${isMockTransport && detail.data.messages.length > 0 ? "mock-composer" : ""}`}>
                <div><strong>Autonomous mode</strong><span>{isMockTransport ? "Local Groq + mock SMS test" : "Groq generates replies from approved context."}</span></div>
                {detail.data.status === "OPEN" && detail.data.messages.length === 0 && <button className="button primary" onClick={() => start.mutate()} disabled={start.isPending}><Send size={17} />{start.isPending ? "Queueing…" : "Start outreach"}</button>}
                {isMockTransport && detail.data.status === "OPEN" && detail.data.messages.length > 0 && <form className="mock-reply-form" onSubmit={(event) => { event.preventDefault(); const body = replyBody.trim(); if (body) mockReply.mutate(body); }}><label className="sr-only" htmlFor="mock-reply">Reply as the lead</label><input id="mock-reply" value={replyBody} onChange={(event) => setReplyBody(event.target.value)} placeholder="Type a reply as the lead…" maxLength={1600} /><button className="button secondary" disabled={mockReply.isPending || !replyBody.trim()}><Send size={16} />{mockReply.isPending ? "Sending…" : "Reply as lead"}</button>{mockReply.error && <p className="inline-error" role="alert">{mockReply.error.message}</p>}</form>}
                {!isMockTransport && detail.data.status === "OPEN" && detail.data.messages.length > 0 && <span className="waiting-copy">Waiting for the lead’s reply.</span>}
                {start.error && <p className="inline-error" role="alert">{start.error.message}</p>}
              </footer>
            </>}
          </section>
        </main>
      </div>
      {showNew && <NewConversationForm onClose={() => setShowNew(false)} onSubmit={(value: ConversationCreate) => create.mutate(value)} pending={create.isPending} error={create.error?.message} />}
      {showBulk && <BulkCampaignForm onClose={() => { setShowBulk(false); bulkLaunch.reset(); }} onSubmit={(value: BulkCampaignCreate) => bulkLaunch.mutate(value)} pending={bulkLaunch.isPending} error={bulkLaunch.error?.message} result={bulkLaunch.data} />}
    </div>
  );
}

function Metric({ icon, label, value }: { icon: ReactNode; label: string; value: number }) {
  return <article className="metric"><div className="metric-icon">{icon}</div><div><span>{label}</span><strong>{value}</strong></div></article>;
}

function ConversationRow({ conversation, active }: { conversation: Conversation; active: boolean }) {
  return <Link className={`conversation-row ${active ? "selected" : ""}`} to={`/sms/${conversation.id}`}><div className="avatar">{initials(conversation.contact_name)}</div><div className="row-copy"><div><strong>{conversation.contact_name}</strong><time>{conversation.last_message_at ? formatter.format(new Date(conversation.last_message_at)) : "New"}</time></div><p>{conversation.outcome?.replaceAll("_", " ") ?? conversation.campaign_objective}</p></div><span className={`status-dot status-dot-${conversation.status.toLowerCase()}`} aria-label={conversation.status} /></Link>;
}

function initials(value: string) { return value.split(/\s+/).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "?"; }
