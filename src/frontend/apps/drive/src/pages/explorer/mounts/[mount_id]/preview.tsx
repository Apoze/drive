import { useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/router";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { APIError } from "@/features/api/APIError";
import { fetchAPI } from "@/features/api/fetchApi";
import { getOrigin } from "@/features/api/utils";
import { getGlobalExplorerLayout } from "@/features/layouts/components/explorer/ExplorerLayout";

type PreviewData = {
  contentType: string;
  apiUrl: string;
  downloadUrl: string;
};

function getParentPath(path: string) {
  if (path === "/") {
    return "/";
  }
  const parts = path.split("/").filter(Boolean);
  parts.pop();
  return `/${parts.join("/")}` || "/";
}

export default function MountPreviewPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const mountId = String(router.query.mount_id ?? "");
  const path = String(router.query.path ?? "");

  const apiUrl = useMemo(() => {
    if (!mountId || !path) {
      return "";
    }
    const origin = getOrigin();
    const query = new URLSearchParams({ path });
    const prefix = origin ? origin : "";
    return `${prefix}/api/v1.0/mounts/${mountId}/preview/?${query.toString()}`;
  }, [mountId, path]);

  const { data, isLoading, error } = useQuery<PreviewData>({
    queryKey: ["mounts", "preview", mountId, path],
    enabled: Boolean(mountId && path),
    refetchOnWindowFocus: false,
    queryFn: async () => {
      const response = await fetchAPI(
        `mounts/${mountId}/preview/`,
        {
          params: { path },
          headers: { Range: "bytes=0-0" },
        },
        { redirectOn40x: false },
      );
      const contentType =
        response.headers.get("Content-Type") ?? "application/octet-stream";
      try {
        // Avoid buffering the full preview response in JS; the UI loads the
        // content directly via <img>/<iframe>.
        await response.body?.cancel();
      } catch {
        // Ignore cancellation errors.
      }
      const origin = getOrigin();
      const prefix = origin ? origin : "";
      const query = new URLSearchParams({ path });
      const downloadUrl = `${prefix}/api/v1.0/mounts/${mountId}/download/?${query.toString()}`;
      return { contentType, apiUrl, downloadUrl };
    },
  });

  const apiErrorCode =
    error instanceof APIError ? error.data?.errors?.[0]?.code : null;

  const showNotAvailable =
    apiErrorCode === "mount.preview.disabled" ||
    apiErrorCode === "mount.preview.unavailable" ||
    apiErrorCode === "mount.preview.not_previewable";

  if (!mountId || !path) {
    return (
      <div>
        <div>{t("explorer.mounts.preview_page.missing_params")}</div>
        <Link href="/explorer/mounts">{t("explorer.mounts.title")}</Link>
      </div>
    );
  }

  if (isLoading) {
    return <div>{t("explorer.mounts.preview_page.loading")}</div>;
  }

  if (showNotAvailable) {
    return (
      <div>
        <h1>{t("explorer.mounts.preview_page.title")}</h1>
        <div>{t("explorer.mounts.preview_page.not_available")}</div>
        <div>{t("explorer.mounts.preview_page.next_action")}</div>
        <Button
          variant="tertiary"
          onClick={() =>
            router.push({
              pathname: "/explorer/mounts/[mount_id]",
              query: { mount_id: mountId, path: getParentPath(path) },
            })
          }
        >
          {t("common.back")}
        </Button>
      </div>
    );
  }

  if (apiErrorCode === "mount.smb.env.auth_failed") {
    return (
      <div>
        <h1>{t("explorer.mounts.preview_page.title")}</h1>
        <div>{t("explorer.mounts.preview_page.access_denied")}</div>
        <Button
          variant="tertiary"
          onClick={() =>
            router.push({
              pathname: "/explorer/mounts/[mount_id]",
              query: { mount_id: mountId, path: getParentPath(path) },
            })
          }
        >
          {t("common.back")}
        </Button>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div>
        <h1>{t("explorer.mounts.preview_page.title")}</h1>
        <div>{t("explorer.mounts.preview_page.error")}</div>
        <Button variant="tertiary" onClick={() => router.reload()}>
          {t("common.retry")}
        </Button>
        <Button
          variant="tertiary"
          onClick={() =>
            router.push({
              pathname: "/explorer/mounts/[mount_id]",
              query: { mount_id: mountId, path: getParentPath(path) },
            })
          }
          style={{ marginLeft: "0.5rem" }}
        >
          {t("common.back")}
        </Button>
      </div>
    );
  }

  const isImage = data.contentType.startsWith("image/");

  return (
    <div>
      <h1>{t("explorer.mounts.preview_page.title")}</h1>
      <div>
        <Link href={data.apiUrl} target="_blank" rel="noreferrer">
          {t("explorer.mounts.preview_page.open_new_tab")}
        </Link>
      </div>
      <div>
        <Link href={data.downloadUrl} target="_blank" rel="noreferrer">
          {t("explorer.mounts.actions.download")}
        </Link>
      </div>
      {isImage ? (
        <img
          src={data.apiUrl}
          alt={t("explorer.mounts.preview_page.title")}
          style={{ maxWidth: "100%" }}
        />
      ) : (
        <iframe
          src={data.apiUrl}
          title={t("explorer.mounts.preview_page.title")}
          style={{ width: "100%", height: "70vh", border: 0 }}
        />
      )}
    </div>
  );
}

MountPreviewPage.getLayout = getGlobalExplorerLayout;
