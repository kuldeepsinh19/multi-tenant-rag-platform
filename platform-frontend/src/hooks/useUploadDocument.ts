import { useMutation, useQueryClient } from "@tanstack/react-query";

import { uploadDocument } from "@/api/documents";
import { documentsQueryKey } from "@/hooks/useDocuments";

export function useUploadDocument(businessId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (file: File) => uploadDocument(businessId, file),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: documentsQueryKey(businessId) });
    },
  });
}
