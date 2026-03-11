import { useEffect, useMemo, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { useTranslation } from "react-i18next";
import { FilePreview, FilePreviewType } from "@/features/ui/preview/files-preview/FilesPreview";
import { WopiInfo, ItemTextContent } from "@/features/drivers/types";
import { getDriver } from "@/features/config/Config";
import { errorToString } from "@/features/api/APIError";
import { ErrorPreview } from "@/features/ui/preview/error/ErrorPreview";
import { InfoRow } from "@/features/ui/components/info/InfoRow";
import { formatSize } from "@/features/explorer/utils/utils";
import {
  getMountExplorerMeta,
  type MountExplorerItem,
} from "@/features/mounts/utils/mountExplorerItems";

type MountPreviewFile = FilePreviewType & {
  mountId: string;
  mountPath: string;
  mountTitle: string;
  provider?: string;
};

type MountFilesPreviewProps = {
  currentItem?: MountExplorerItem;
  items: MountExplorerItem[];
  setPreviewItem?: (item?: MountExplorerItem) => void;
};

const itemToMountPreviewFile = (item: MountExplorerItem): MountPreviewFile => {
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

const MountWopiEditor = ({ file }: { file: MountPreviewFile }) => {
  const { t } = useTranslation();
  const formRef = useRef<HTMLFormElement>(null);
  const {
    data: wopiInfo,
    isLoading,
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

  if (isLoading) {
    return <div>{t("file_preview.wopi.loading")}</div>;
  }

  if (error || !wopiInfo) {
    return (
      <div>
        <div>{errorToString(error)}</div>
        <Button variant="tertiary" onClick={() => refetch()}>
          {t("common.retry")}
        </Button>
        <ErrorPreview file={file} />
      </div>
    );
  }

  useEffect(() => {
    if (wopiInfo && formRef.current) {
      formRef.current.submit();
    }
  }, [wopiInfo]);

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
        name="office_frame"
        className="wopi-editor-iframe"
        title={file.title}
        allow="clipboard-read *; clipboard-write *"
      />
    </div>
  );
};

const MountPreviewSidebar = ({ item }: { item: MountExplorerItem }) => {
  const { t } = useTranslation();
  const meta = getMountExplorerMeta(item);

  return (
    <div className="explorer__right-panel">
      <div className="explorer__right-panel__section p">
        <InfoRow label={t("explorer.mounts.path")} rightContent={meta.normalizedPath} />
        <InfoRow
          label={t("explorer.mounts.provider")}
          rightContent={meta.provider ?? meta.mountTitle}
        />
        {item.size ? (
          <InfoRow
            label={t("explorer.rightPanel.size")}
            rightContent={formatSize(item.size)}
          />
        ) : null}
      </div>
    </div>
  );
};

export const MountFilesPreview = ({
  currentItem,
  items,
  setPreviewItem,
}: MountFilesPreviewProps) => {
  const { t } = useTranslation();

  const files = useMemo(
    () =>
      items
        .filter((item) => item.type === "file")
        .map((item) => itemToMountPreviewFile(item)),
    [items],
  );

  const handleClosePreview = () => {
    setPreviewItem?.(undefined);
  };

  const handleChangePreviewItem = (file?: FilePreviewType) => {
    const nextItem = items.find((item) => item.id === file?.id);
    setPreviewItem?.(nextItem);
  };

  const fetchTextContent = async (
    file: FilePreviewType,
  ): Promise<ItemTextContent | null> => {
    const mountFile = file as MountPreviewFile;
    if (!mountFile.url_preview) {
      return null;
    }
    const response = await fetch(mountFile.url_preview, {
      credentials: "include",
    });
    if (!response.ok) {
      throw new Error(`Unable to preview ${mountFile.title}`);
    }
    const content = await response.text();
    return {
      content,
      truncated: false,
      size: content.length,
      max_preview_bytes: content.length,
      etag: "",
      read_only: true,
    };
  };

  return (
    <FilePreview
      isOpen={!!currentItem}
      onClose={handleClosePreview}
      title={t("file_preview.title")}
      files={files}
      openedFileId={currentItem?.id}
      onChangeFile={handleChangePreviewItem}
      handleDownloadFile={(file) => {
        if (file?.url) {
          window.open(file.url, "_blank", "noreferrer");
        }
      }}
      fetchTextContent={fetchTextContent}
      getTextQueryKey={(file) => ["mounts", "preview", "text", file.id]}
      renderWopiEditor={(file) => <MountWopiEditor file={file as MountPreviewFile} />}
      sidebarContent={currentItem ? <MountPreviewSidebar item={currentItem} /> : undefined}
    />
  );
};
