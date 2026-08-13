/**
 * Single typed API client. All backend calls go through here — never scattered
 * `fetch()` calls in components. One place for base URL, auth headers, and error
 * normalization. See react-frontend-standards.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
}

let authToken: string | null = null;

export function setAuthToken(token: string | null): void {
  authToken = token;
}

/** Exposed so the small sanctioned exceptions to apiRequest (multipart upload,
 * SSE chat streaming — see react-frontend-standards) can still attach the same
 * bearer token without duplicating auth state. */
export function getAuthToken(): string | null {
  return authToken;
}

export const API_BASE_URL_VALUE = API_BASE_URL;

async function throwIfNotOk(response: Response): Promise<void> {
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      payload.error ?? "UnknownError",
      payload.message ?? "Something went wrong. Please try again.",
    );
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (authToken) headers.Authorization = `Bearer ${authToken}`;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  });

  await throwIfNotOk(response);

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/**
 * Multipart file upload exception to the JSON-only apiRequest helper.
 * The base helper always forces `Content-Type: application/json` and
 * JSON.stringifies the body, which breaks FormData uploads (the browser
 * must set its own multipart boundary in Content-Type). This keeps the same
 * auth token, base URL, and ApiError normalization as apiRequest so callers
 * get consistent error handling.
 */
export async function apiRequestMultipart<T>(
  path: string,
  formData: FormData,
  options: { signal?: AbortSignal } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (authToken) headers.Authorization = `Bearer ${authToken}`;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers,
    body: formData,
    signal: options.signal,
  });

  await throwIfNotOk(response);

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
