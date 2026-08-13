import { useMutation } from "@tanstack/react-query";

import { login, type LoginRequest } from "@/api/auth";
import { useAuthStore } from "@/store/auth";

export function useLogin() {
  const storeLogin = useAuthStore((state) => state.login);

  return useMutation({
    mutationFn: (payload: LoginRequest) => login(payload),
    onSuccess: (data) => {
      storeLogin({
        token: data.access_token,
        role: data.role,
        businessId: data.business_id,
      });
    },
  });
}
