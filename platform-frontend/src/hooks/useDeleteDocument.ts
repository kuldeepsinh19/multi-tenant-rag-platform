import { useMutation, useQueryClient } from "@tanstack/react-query";

import { deleteDocument } from "@/api/documents";
import { documentsQueryKey } from "@/hooks/useDocuments";

export function useDeleteDocument(businessId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (documentId: string) => deleteDocument(businessId, documentId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: documentsQueryKey(businessId) });
    },
  });
}
