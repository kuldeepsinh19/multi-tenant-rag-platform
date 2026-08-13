import { apiRequest } from "@/api/client";

export type Role = "super_admin" | "business_admin";

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  role: Role;
  business_id: string | null;
}

export function login(payload: LoginRequest, signal?: AbortSignal): Promise<LoginResponse> {
  return apiRequest<LoginResponse>("/auth/login", {
    method: "POST",
    body: payload,
    signal,
  });
}
