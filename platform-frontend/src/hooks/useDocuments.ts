import { useQuery } from "@tanstack/react-query";

import { fetchDocuments, type Document } from "@/api/documents";

export function documentsQueryKey(businessId: string) {
  return ["documents", businessId] as const;
}

function hasInFlightDocument(documents: Document[]): boolean {
  return documents.some((doc) => doc.status === "pending" || doc.status === "processing");
}

/**
 * Polls every 3s while any document is still pending/processing, and stops
 * polling once every document has settled into ready/failed (or the list is
 * empty) — avoids hammering the backend once there's nothing left to watch.
 */
export function useDocuments(businessId: string | undefined) {
  return useQuery({
    queryKey: documentsQueryKey(businessId ?? ""),
    queryFn: ({ signal }) => fetchDocuments(businessId as string, signal),
    enabled: Boolean(businessId),
    refetchInterval: (query) => {
      const documents = query.state.data;
      if (!documents || documents.length === 0) return false;
      return hasInFlightDocument(documents) ? 3000 : false;
    },
  });
}
