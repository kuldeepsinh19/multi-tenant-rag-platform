import { useQuery } from "@tanstack/react-query";

import { fetchBusiness } from "@/api/businesses";

export function businessQueryKey(id: string) {
  return ["business", id] as const;
}

export function useBusiness(id: string | undefined) {
  return useQuery({
    queryKey: businessQueryKey(id ?? ""),
    queryFn: ({ signal }) => fetchBusiness(id as string, signal),
    enabled: Boolean(id),
  });
}
