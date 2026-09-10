import { useEffect } from "react";
import { useRouter } from "next/router";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { resolveLegacyMount } from "./api";

/** Resolve old bookmarks through current space grants before replacing the URL. */
export const LegacyStorageRoute = () => {
  const router = useRouter();
  const { t } = useTranslation();
  const mountId =
    typeof router.query.mount_id === "string" ? router.query.mount_id : "";
  const path = typeof router.query.path === "string" ? router.query.path : "/";
  const resolved = useQuery({
    queryKey: ["storage", "legacy", mountId, path],
    enabled: router.isReady && Boolean(mountId),
    retry: false,
    queryFn: () => resolveLegacyMount(mountId, path),
  });
  useEffect(() => {
    if (!router.isReady) return;
    if (!mountId) void router.replace("/explorer/items/my-files");
    else if (resolved.data) void router.replace(resolved.data.href);
  }, [router.isReady, mountId, resolved.data, router]);
  return (
    <p role={resolved.isError ? "alert" : "status"}>
      {t(resolved.isError ? "storage.load_error" : "storage.loading")}
    </p>
  );
};
