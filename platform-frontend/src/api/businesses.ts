import { apiRequest } from "@/api/client";

export type BusinessStatus = "active" | "suspended";

export interface Business {
  id: string;
  name: string;
  slug: string;
  status: BusinessStatus;
  plan: string;
  created_at: string;
}

export interface CreateBusinessRequest {
  name: string;
}

export interface InviteAdminRequest {
  email: string;
  password: string;
}

export interface AdminAccount {
  id: string;
  email: string;
  role: string;
  business_id: string;
  created_at: string;
}

export interface CreateWidgetKeyRequest {
  allowed_domains: string[];
}

export interface WidgetKey {
  id: string;
  public_key: string;
  allowed_domains: string[];
  is_active: boolean;
  created_at: string;
}

export function fetchBusinesses(signal?: AbortSignal): Promise<Business[]> {
  return apiRequest<Business[]>("/businesses", { signal });
}

export function createBusiness(
  payload: CreateBusinessRequest,
  signal?: AbortSignal,
): Promise<Business> {
  return apiRequest<Business>("/businesses", { method: "POST", body: payload, signal });
}

export function fetchBusiness(id: string, signal?: AbortSignal): Promise<Business> {
  return apiRequest<Business>(`/businesses/${id}`, { signal });
}

export function inviteAdmin(
  businessId: string,
  payload: InviteAdminRequest,
  signal?: AbortSignal,
): Promise<AdminAccount> {
  return apiRequest<AdminAccount>(`/businesses/${businessId}/admins`, {
    method: "POST",
    body: payload,
    signal,
  });
}

export function createWidgetKey(
  businessId: string,
  payload: CreateWidgetKeyRequest,
  signal?: AbortSignal,
): Promise<WidgetKey> {
  return apiRequest<WidgetKey>(`/businesses/${businessId}/widget-keys`, {
    method: "POST",
    body: payload,
    signal,
  });
}

export interface BusinessMetrics {
  total_messages: number;
  total_tokens: number;
  total_cost_usd: number;
  avg_latency_ms: number;
  groundedness_pass_rate: number;
}

export function fetchMetrics(businessId: string, signal?: AbortSignal): Promise<BusinessMetrics> {
  return apiRequest<BusinessMetrics>(`/businesses/${businessId}/metrics`, { signal });
}
