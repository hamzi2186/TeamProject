import { FormEvent, useMemo, useState } from "react";
import { Database, X } from "lucide-react";
import type { BulkCampaignCreate, BulkCampaignResult, BulkLead } from "../../types/sms";

const campaign = {
  campaign_id: "44444444-4444-4444-8444-444444444444",
  from_number: "+15555550100",
  message_template: "Hi {{first_name}}, this is Alex from FlowPilot. Are you still looking for a faster way to follow up with new leads?",
  campaign_objective: "Book a 20-minute product demonstration with interested operations teams.",
  knowledge_context: "FlowPilot is a fictional demo product for this local test. It helps small service businesses respond to imported web leads with personalized SMS messages, record the conversation, and schedule follow-up reminders. The demonstration takes 20 minutes and can be booked Monday through Friday from 9 AM to 5 PM Eastern Time. Do not quote pricing, discounts, guarantees, or customer names. If asked about pricing, say that pricing depends on team size and can be discussed during the demo.",
  max_agent_turns: 6,
};

const importedLeads: BulkLead[] = [
  { lead_id: "55555555-5555-4555-8555-555555555555", first_name: "Sam", contact_name: "Sam Carter", phone_number: "+15555550111", timezone: "America/Los_Angeles", consented: true, consent_source: "demo_hubspot_import" },
  { lead_id: "66666666-6666-4666-8666-666666666666", first_name: "Jordan", contact_name: "Jordan Lee", phone_number: "+15555550112", timezone: "America/Los_Angeles", consented: true, consent_source: "demo_hubspot_import" },
];

export function BulkCampaignForm({
  onClose,
  onSubmit,
  pending,
  error,
  result,
}: {
  onClose: () => void;
  onSubmit: (value: BulkCampaignCreate) => void;
  pending: boolean;
  error?: string;
  result?: BulkCampaignResult;
}) {
  const [selected, setSelected] = useState(() => new Set(importedLeads.map((lead) => lead.lead_id)));
  const selectedLeads = useMemo(() => importedLeads.filter((lead) => selected.has(lead.lead_id)), [selected]);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit({ ...campaign, start_immediately: true, leads: selectedLeads });
  };
  const toggle = (leadId: string) => setSelected((current) => {
    const next = new Set(current);
    if (next.has(leadId)) next.delete(leadId);
    else next.add(leadId);
    return next;
  });

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal bulk-modal" role="dialog" aria-modal="true" aria-labelledby="bulk-title">
        <header className="modal-header">
          <div><p className="eyebrow">Bulk launch</p><h2 id="bulk-title">Select imported leads</h2></div>
          <button className="icon-button" onClick={onClose} aria-label="Close dialog"><X size={20} /></button>
        </header>
        <form onSubmit={submit} className="bulk-form">
          <div className="source-banner"><Database size={18} /><div><strong>Demo HubSpot import</strong><span>This fixture will be replaced by the shared contacts API.</span></div></div>
          <div className="bulk-summary"><div><span>Campaign</span><strong>FlowPilot demo follow-up</strong></div><div><span>Selected</span><strong>{selectedLeads.length} of {importedLeads.length}</strong></div></div>
          <div className="lead-table" role="group" aria-label="Imported leads">
            <label className="lead-row lead-row-header"><input type="checkbox" checked={selected.size === importedLeads.length} onChange={(event) => setSelected(new Set(event.target.checked ? importedLeads.map((lead) => lead.lead_id) : []))} /><span>Lead</span><span>Phone</span><span>Consent</span></label>
            {importedLeads.map((lead) => <label className="lead-row" key={lead.lead_id}><input type="checkbox" checked={selected.has(lead.lead_id)} onChange={() => toggle(lead.lead_id)} /><span><strong>{lead.contact_name}</strong><small>{lead.timezone}</small></span><span>{lead.phone_number}</span><span className="consent-ok">Recorded</span></label>)}
          </div>
          {result && <div className="bulk-result" role="status">Queued {result.queued.length}. Created {result.created.length}. Skipped {result.skipped.length}.</div>}
          {error && <div className="form-error" role="alert">{error}</div>}
          <footer className="modal-actions"><button type="button" className="button secondary" onClick={onClose}>Close</button><button className="button primary" disabled={pending || selectedLeads.length === 0}>{pending ? "Launching…" : `Launch to ${selectedLeads.length} leads`}</button></footer>
        </form>
      </section>
    </div>
  );
}
