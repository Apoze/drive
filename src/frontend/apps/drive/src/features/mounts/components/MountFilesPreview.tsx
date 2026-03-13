import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { FilePreview } from "@/features/ui/preview/files-preview/FilesPreview";
import { InfoRow } from "@/features/ui/components/info/InfoRow";
import { formatSize } from "@/features/explorer/utils/utils";
import {
  getMountExplorerMeta,
  type MountExplorerItem,
} from "@/features/mounts/utils/mountExplorerItems";
import { type FilePreviewType } from "@/features/ui/preview/files-preview/previewSource";
import {
  itemToMountPreviewFile,
  useMountPreviewSource,
} from "@/features/mounts/components/useMountPreviewSource";

type MountFilesPreviewProps = {
  currentItem?: MountExplorerItem;
  items: MountExplorerItem[];
  setPreviewItem?: (item?: MountExplorerItem) => void;
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
  const previewSource = useMountPreviewSource();

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
      source={previewSource}
      sidebarContent={currentItem ? <MountPreviewSidebar item={currentItem} /> : undefined}
    />
  );
};
