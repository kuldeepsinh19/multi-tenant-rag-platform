import { useQuery } from "@tanstack/react-query";

import { fetchMetrics } from "@/api/businesses";

export function useMetrics(businessId: string | undefined) {
  return useQuery({
    queryKey: ["metrics", businessId ?? ""],
    queryFn: ({ signal }) => fetchMetrics(businessId as string, signal),
    enabled: Boolean(businessId),
  });
}
