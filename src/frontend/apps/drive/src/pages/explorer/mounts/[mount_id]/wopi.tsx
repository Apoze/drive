import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/router";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { getDriver } from "@/features/config/Config";
import { useConfig } from "@/features/config/ConfigProvider";
import { APIError, errorToString } from "@/features/api/APIError";
import { getOperationTimeBound } from "@/features/operations/timeBounds";
import { useTimeBoundedPhase } from "@/features/operations/useTimeBoundedPhase";
import { getGlobalExplorerLayout } from "@/features/layouts/components/explorer/ExplorerLayout";

function getParentPath(path: string) {
  if (path === "/") {
    return "/";
  }
  const parts = path.split("/").filter(Boolean);
  parts.pop();
  return `/${parts.join("/")}` || "/";
}

export default function MountWopiPage() {
  const { t } = useTranslation();
  const { config } = useConfig();
  const router = useRouter();
  const mountId = String(router.query.mount_id ?? "");
  const path = String(router.query.path ?? "");

  const formRef = useRef<HTMLFormElement>(null);
  const [iframeLoaded, setIframeLoaded] = useState(false);
  const [iframeKey, setIframeKey] = useState(0);

  const filename = useMemo(() => {
    const parts = path.split("/").filter(Boolean);
    return parts[parts.length - 1] ?? "Document";
  }, [path]);

  const wopiInfoBounds = useMemo(
    () => getOperationTimeBound("wopi_info", config),
    [config],
  );
  const wopiIframeBounds = useMemo(
    () => getOperationTimeBound("wopi_iframe", config),
    [config],
  );

  const {
    data: wopiInfo,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["mounts", mountId, "wopi", path],
    enabled: Boolean(mountId && path),
    refetchOnWindowFocus: false,
    queryFn: () => getDriver().getMountWopiInfo({ mountId, path }),
  });

  useEffect(() => {
    if (wopiInfo && formRef.current) {
      setIframeLoaded(false);
      formRef.current.submit();
    }
  }, [wopiInfo]);

  const infoPhase = useTimeBoundedPhase(isLoading, wopiInfoBounds);
  const iframePhase = useTimeBoundedPhase(
    Boolean(wopiInfo) && !iframeLoaded,
    wopiIframeBounds,
  );

  if (!mountId || !path) {
    return (
      <div>
        <div>{t("explorer.mounts.preview_page.missing_params")}</div>
        <Link href="/explorer/mounts">{t("explorer.mounts.title")}</Link>
      </div>
    );
  }

  if (isLoading) {
    if (infoPhase === "loading") {
      return <div>{t("file_preview.wopi.loading")}</div>;
    }
    return (
      <div>
        <div>
          {infoPhase === "still_working"
            ? t("operations.long_running.still_working")
            : t("operations.long_running.failed")}
        </div>
        <Button variant="tertiary" onClick={() => refetch()}>
          {t("common.retry")}
        </Button>
      </div>
    );
  }

  if (isError || !wopiInfo) {
    const apiCode =
      error instanceof APIError ? error.data?.errors?.[0]?.code : null;
    const unavailableKey =
      apiCode === "wopi.not_enabled"
        ? "not_enabled"
        : apiCode === "wopi.discovery_missing"
          ? "discovery_missing"
          : apiCode === "wopi.file_unavailable"
            ? "file_unavailable"
            : null;

    const message = unavailableKey
      ? t(`file_preview.wopi.unavailable.${unavailableKey}`)
      : errorToString(error);

    return (
      <div>
        <h1>{t("explorer.mounts.actions.wopi")}</h1>
        <div>{message}</div>
        <div style={{ marginTop: "1rem" }}>
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
          <Button
            variant="tertiary"
            onClick={() => refetch()}
            style={{ marginLeft: "0.5rem" }}
          >
            {t("common.retry")}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="wopi-editor">
      <div style={{ marginBottom: "0.5rem" }}>
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
      <form
        ref={formRef}
        name="office_form"
        target="office_frame"
        action={wopiInfo.launch_url}
        method="post"
      >
        <input name="access_token" value={wopiInfo.access_token} type="hidden" />
        <input
          name="access_token_ttl"
          value={wopiInfo.access_token_ttl}
          type="hidden"
        />
      </form>
      <iframe
        key={iframeKey}
        name="office_frame"
        className="wopi-editor-iframe"
        title={filename}
        onLoad={() => setIframeLoaded(true)}
      />
      {!iframeLoaded && (
        <div>
          {iframePhase === "loading" ? (
            <div>{t("file_preview.wopi.loading")}</div>
          ) : iframePhase === "still_working" ? (
            <div>{t("operations.long_running.still_working")}</div>
          ) : (
            <div>
              <div>{t("operations.long_running.failed")}</div>
              <Button
                variant="tertiary"
                onClick={() => {
                  setIframeKey((k) => k + 1);
                  refetch();
                }}
              >
                {t("common.retry")}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

MountWopiPage.getLayout = getGlobalExplorerLayout;
