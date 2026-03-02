import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getDriver } from "@/features/config/Config";
import { FilePreviewType } from "../files-preview/FilesPreview";
import { ErrorPreview } from "../error/ErrorPreview";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { useConfig } from "@/features/config/ConfigProvider";
import { getOperationTimeBound } from "@/features/operations/timeBounds";
import { useTimeBoundedPhase } from "@/features/operations/useTimeBoundedPhase";
import { APIError, errorToString } from "@/features/api/APIError";

interface WopiEditorProps {
  item: FilePreviewType;
  onFileRename?: (file: FilePreviewType, newName: string) => void;
}

export const WopiEditor = ({ item, onFileRename }: WopiEditorProps) => {
  const { t } = useTranslation();
  const { config } = useConfig();
  const queryClient = useQueryClient();
  const formRef = useRef<HTMLFormElement>(null);
  const [iframeLoaded, setIframeLoaded] = useState(false);
  const [iframeKey, setIframeKey] = useState(0);

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
    queryKey: ["item", item.id, "wopi"],
    refetchOnWindowFocus: false,
    queryFn: () => getDriver().getWopiInfo(item.id),
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

  // Listen for PostMessage events from the WOPI editor.
  // At the moment only OnlyOffice supports this feature as Collabora
  // does not post messages when renaming a file.
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      let data = event.data;
      if (typeof data === "string") {
        try {
          data = JSON.parse(data);
        } catch {
          return;
        }
      }

      if (!data || typeof data !== "object" || !data.MessageId) {
        return;
      }

      // Handle rename notifications from the WOPI editor
      if (data.MessageId === "File_Rename") {
        onFileRename?.(item, data.Values.NewName);
      }
    };

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [item, onFileRename, queryClient]);

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
        : apiCode === "wopi.backend_unsupported"
          ? "backend_unsupported"
          : apiCode === "wopi.discovery_missing"
            ? "discovery_missing"
            : apiCode === "wopi.file_unavailable"
              ? "file_unavailable"
              : null;

    const message = unavailableKey
      ? t(`file_preview.wopi.unavailable.${unavailableKey}`)
      : errorToString(error);
    const nextAction =
      unavailableKey === "not_enabled" || unavailableKey === "backend_unsupported"
        ? "contact_admin"
        : "retry";

    return (
      <div>
        <div>{message}</div>
        {nextAction === "retry" ? (
          <Button variant="tertiary" onClick={() => refetch()}>
            {t("common.retry")}
          </Button>
        ) : (
          <div>{t("common.contact_admin")}</div>
        )}
        <ErrorPreview file={item} />
      </div>
    );
  }

  return (
    <div className="wopi-editor">
      <form
        ref={formRef}
        name="office_form"
        target="office_frame"
        action={wopiInfo.launch_url}
        method="post"
      >
        <input
          name="access_token"
          value={wopiInfo.access_token}
          type="hidden"
        />
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
        title={item.title}
        onLoad={() => setIframeLoaded(true)}
        allow="clipboard-read *; clipboard-write *"
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
};
