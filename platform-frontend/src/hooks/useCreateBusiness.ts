import { useMutation, useQueryClient } from "@tanstack/react-query";

import { createBusiness, type CreateBusinessRequest } from "@/api/businesses";
import { businessesQueryKey } from "@/hooks/useBusinesses";

export function useCreateBusiness() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: CreateBusinessRequest) => createBusiness(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: businessesQueryKey });
    },
  });
}
