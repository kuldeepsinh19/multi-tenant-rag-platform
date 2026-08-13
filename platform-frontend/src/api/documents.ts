import { apiRequest, apiRequestMultipart } from "@/api/client";

export type DocumentStatus = "pending" | "processing" | "ready" | "failed";

export interface Document {
  id: string;
  business_id: string;
  filename: string;
  mime_type: string;
  status: DocumentStatus;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export function fetchDocuments(businessId: string, signal?: AbortSignal): Promise<Document[]> {
  return apiRequest<Document[]>(`/businesses/${businessId}/documents`, { signal });
}

export function uploadDocument(
  businessId: string,
  file: File,
  signal?: AbortSignal,
): Promise<Document> {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequestMultipart<Document>(`/businesses/${businessId}/documents`, formData, {
    signal,
  });
}

export function deleteDocument(
  businessId: string,
  documentId: string,
  signal?: AbortSignal,
): Promise<void> {
  return apiRequest<void>(`/businesses/${businessId}/documents/${documentId}`, {
    method: "DELETE",
    signal,
  });
}
