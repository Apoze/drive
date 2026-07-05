import React from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { useTranslation } from "react-i18next";
import { useConfig } from "@/features/config/ConfigProvider";
import { getDriver } from "@/features/config/Config";
import { APIError, errorToString } from "@/features/api/APIError";
import { getOperationTimeBound } from "@/features/operations/timeBounds";
import { useTimeBoundedPhase } from "@/features/operations/useTimeBoundedPhase";
import { ErrorPreview } from "@/features/ui/preview/error/ErrorPreview";
import { ArchiveViewer } from "@/features/ui/preview/archive-viewer/ArchiveViewer";
import { WopiInfo, ItemTextContent, MountPreviewInfo } from "@/features/drivers/types";
import {
  type FilePreviewType,
  type PreviewSource,
} from "@/features/ui/preview/files-preview/previewSource";
import {
  getMountExplorerMeta,
  type MountExplorerItem,
} from "@/features/mounts/utils/mountExplorerItems";

export type MountPreviewFile = FilePreviewType & {
  mountId: string;
  mountPath: string;
  mountTitle: string;
  provider?: string;
};

export const itemToMountPreviewFile = (
  item: MountExplorerItem,
): MountPreviewFile => {
  const meta = getMountExplorerMeta(item);
  return {
    id: item.id,
    title: item.title,
    filename: item.filename,
    mimetype: item.mimetype ?? "application/octet-stream",
    url_preview: item.url_preview,
    url: item.url,
    is_wopi_supported: Boolean(meta.abilities?.wopi),
    size: item.size ?? 0,
    can_update: false,
    mountId: meta.mountId,
    mountPath: meta.normalizedPath,
    mountTitle: meta.mountTitle,
    provider: meta.provider,
  };
};

const previewInfoToFilePatch = (
  file: MountPreviewFile,
  previewInfo: MountPreviewInfo,
): Partial<MountPreviewFile> => {
  const streamUrl = previewInfo.stream_url ?? undefined;
  return {
    mimetype: previewInfo.mimetype,
    is_wopi_supported: previewInfo.is_wopi_supported,
    url_preview: streamUrl ?? previewInfo.inline_url ?? undefined,
    url: previewInfo.download_url ?? file.url,
    stream_url: streamUrl,
    stream_expires_at: previewInfo.stream_expires_at ?? undefined,
    preview_kind: previewInfo.preview_kind,
    can_update: previewInfo.can_edit_text,
  };
};

const MountWopiEditor = ({
  file,
  onDownload,
}: {
  file: MountPreviewFile;
  onDownload?: () => void;
}) => {
  const { t } = useTranslation();
  const { config } = useConfig();
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
  } = useQuery<WopiInfo>({
    queryKey: ["mounts", file.mountId, "wopi", file.mountPath],
    refetchOnWindowFocus: false,
    queryFn: () =>
      getDriver().getMountWopiInfo({
        mountId: file.mountId,
        path: file.mountPath,
      }),
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
        : apiCode === "wopi.backend_unsupported" || apiCode === "mount.wopi.disabled"
          ? "backend_unsupported"
          : apiCode === "wopi.discovery_missing"
            ? "discovery_missing"
            : apiCode === "wopi.file_unavailable" || apiCode === "mount.wopi.unavailable"
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
        <ErrorPreview file={file} onDownload={onDownload} />
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
          readOnly
        />
        <input
          name="access_token_ttl"
          value={wopiInfo.access_token_ttl}
          type="hidden"
          readOnly
        />
      </form>
      <iframe
        key={iframeKey}
        name="office_frame"
        className="wopi-editor-iframe"
        title={file.title}
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

export const useMountPreviewSource = () =>
  useMemo<PreviewSource>(
    () => ({
      async fetchTextContent(file: FilePreviewType): Promise<ItemTextContent | null> {
        const mountFile = file as MountPreviewFile;
        return getDriver().getMountText({
          mountId: mountFile.mountId,
          path: mountFile.mountPath,
        });
      },
      getTextQueryKey(file: FilePreviewType) {
        return ["mounts", "preview", "text", file.id];
      },
      async saveTextContent({
        file,
        content,
        etag,
      }: {
        file: FilePreviewType;
        content: string;
        etag: string;
      }) {
        const mountFile = file as MountPreviewFile;
        return getDriver().saveMountText({
          mountId: mountFile.mountId,
          path: mountFile.mountPath,
          content,
          etag,
        });
      },
      async resolveFilePreview(file: FilePreviewType) {
        const mountFile = file as MountPreviewFile;
        const previewInfo = await getDriver().getMountPreviewInfo({
          mountId: mountFile.mountId,
          path: mountFile.mountPath,
        });
        return previewInfoToFilePatch(mountFile, previewInfo);
      },
      getResolveFilePreviewQueryKey(file: FilePreviewType) {
        const mountFile = file as MountPreviewFile;
        return ["mounts", mountFile.mountId, "preview-info", mountFile.mountPath];
      },
      renderWopiEditor(file: FilePreviewType, _onFileRename, onDownload?: () => void) {
        return (
          <MountWopiEditor
            file={file as MountPreviewFile}
            onDownload={onDownload}
          />
        );
      },
      renderArchiveViewer(file: FilePreviewType, onDownload?: () => void) {
        return (
          <ArchiveViewer
            archiveItem={{
              id: file.id,
              title: file.title,
              size: file.size,
              mimetype: file.mimetype,
              url: file.stream_url ?? file.url,
            }}
            archiveAccessMode={file.stream_url ? "auto" : "download"}
            allowExtraction={false}
            onDownloadArchive={onDownload}
          />
        );
      },
    }),
    [],
  );
