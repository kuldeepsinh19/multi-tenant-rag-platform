import { useMutation } from "@tanstack/react-query";

import { inviteAdmin, type InviteAdminRequest } from "@/api/businesses";

export function useInviteAdmin(businessId: string) {
  return useMutation({
    mutationFn: (payload: InviteAdminRequest) => inviteAdmin(businessId, payload),
  });
}
