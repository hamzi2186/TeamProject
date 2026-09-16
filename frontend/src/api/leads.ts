import { apiRequest } from "./client";

export type Lead = {
  id: string;
  hubspot_contact_id: string;
  first_name: string | null;
  last_name: string | null;
  display_name: string | null;
  phone: string | null;
  email: string | null;
  website_url: string | null;
  website_id: string | null;
  current_status: string;
  created_at: string;
  updated_at: string;
};

export const leadsApi = {
  list: () => apiRequest<Lead[]>("/api/v1/leads"),
  detail: (leadId: string) => apiRequest<Lead>(`/api/v1/leads/${leadId}`),
};
