import { FormEvent, useState } from "react";
import { X } from "lucide-react";
import type { ConversationCreate } from "../../types/sms";

const initialForm: ConversationCreate = {
  campaign_id: "11111111-1111-4111-8111-111111111111",
  lead_id: "22222222-2222-4222-8222-222222222222",
  contact_name: "Demo lead",
  from_number: "+15555550100",
  to_number: "+15555550101",
  timezone: "America/New_York",
  message_template: "Hi {{first_name}}, I wanted to reach out about {{campaign_objective}}.",
  campaign_objective: "Introduce the service and learn whether the lead is interested.",
  knowledge_context: "Replace this fixture with approved Client KB context.",
  consent_source: "demo_fixture",
  consented: true,
  max_agent_turns: 8,
};

export function NewConversationForm({
  onClose,
  onSubmit,
  pending,
  error,
}: {
  onClose: () => void;
  onSubmit: (value: ConversationCreate) => void;
  pending: boolean;
  error?: string;
}) {
  const [form, setForm] = useState(initialForm);
  const update = <K extends keyof ConversationCreate>(key: K, value: ConversationCreate[K]) =>
    setForm((current) => ({ ...current, [key]: value }));
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit(form);
  };

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal" role="dialog" aria-modal="true" aria-labelledby="new-title">
        <header className="modal-header">
          <div><p className="eyebrow">Demo fixture</p><h2 id="new-title">New SMS conversation</h2></div>
          <button className="icon-button" onClick={onClose} aria-label="Close dialog"><X size={20} /></button>
        </header>
        <form onSubmit={submit} className="conversation-form">
          <label>Contact name<input value={form.contact_name} onChange={(e) => update("contact_name", e.target.value)} required /></label>
          <div className="field-row">
            <label>SMS sender<input type="tel" value={form.from_number} onChange={(e) => update("from_number", e.target.value)} required /></label>
            <label>Recipient<input type="tel" value={form.to_number} onChange={(e) => update("to_number", e.target.value)} required /></label>
          </div>
          <label>Campaign objective<textarea value={form.campaign_objective} onChange={(e) => update("campaign_objective", e.target.value)} required /></label>
          <label>Opening template<textarea value={form.message_template} onChange={(e) => update("message_template", e.target.value)} required /></label>
          <label>Approved KB context<textarea value={form.knowledge_context} onChange={(e) => update("knowledge_context", e.target.value)} /></label>
          <label className="checkbox"><input type="checkbox" checked={form.consented} onChange={(e) => update("consented", e.target.checked)} /><span>This lead has recorded SMS consent</span></label>
          {error && <div className="form-error" role="alert">{error}</div>}
          <footer className="modal-actions"><button type="button" className="button secondary" onClick={onClose}>Cancel</button><button className="button primary" disabled={pending}>{pending ? "Creating…" : "Create conversation"}</button></footer>
        </form>
      </section>
    </div>
  );
}
