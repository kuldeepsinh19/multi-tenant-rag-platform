import { useMutation } from "@tanstack/react-query";

import { createWidgetKey, type CreateWidgetKeyRequest } from "@/api/businesses";

export function useCreateWidgetKey(businessId: string) {
  return useMutation({
    mutationFn: (payload: CreateWidgetKeyRequest) => createWidgetKey(businessId, payload),
  });
}
