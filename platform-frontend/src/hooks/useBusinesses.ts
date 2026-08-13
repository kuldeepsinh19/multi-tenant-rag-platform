import { useQuery } from "@tanstack/react-query";

import { fetchBusinesses } from "@/api/businesses";

export const businessesQueryKey = ["businesses"] as const;

export function useBusinesses() {
  return useQuery({
    queryKey: businessesQueryKey,
    queryFn: ({ signal }) => fetchBusinesses(signal),
  });
}
