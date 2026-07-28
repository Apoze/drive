import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/features/auth/Auth";
import { getEntitlements } from "@/utils/entitlements";

export const useEntitlementsQuery = () => {
  const { user } = useAuth();
  return useQuery({
    queryKey: ["entitlements"],
    queryFn: getEntitlements,
    enabled: Boolean(user),
    staleTime: 60_000,
  });
};
