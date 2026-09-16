import { apiRequest } from "./client";

export type HubSpotStatus = {
  status: string;
  connected: boolean;
  portal_id: string | null;
  scopes: string[];
  created_at: string | null;
  updated_at: string | null;
  expires_at: string | null;
};

export type HubSpotContact = {
  provider_contact_id: string;
  firstname: string | null;
  lastname: string | null;
  phone: string | null;
  email: string | null;
  website: string | null;
};

type ContactPage = { contacts: HubSpotContact[]; next_after: string | null };
export type ImportResult = { imported: number; created: number; updated: number };

export const hubspotApi = {
  status: () => apiRequest<HubSpotStatus>("/api/v1/hubspot/status"),
  connect: () =>
    apiRequest<{ authorization_url: string; expires_in: number }>("/api/v1/hubspot/connect"),
  contacts: (after?: string) =>
    apiRequest<ContactPage>(`/api/v1/hubspot/contacts${after ? `?after=${encodeURIComponent(after)}` : ""}`),
  importContacts: (hubspotContactIds: string[], selectAll: boolean) =>
    apiRequest<ImportResult>("/api/v1/hubspot/import", {
      method: "POST",
      body: JSON.stringify({ hubspot_contact_ids: hubspotContactIds, select_all: selectAll }),
    }),
};
