import React from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { FilePreview } from "@/features/ui/preview/files-preview/FilesPreview";
import { InfoRow } from "@/features/ui/components/info/InfoRow";
import { formatSize } from "@/features/explorer/utils/utils";
import {
  getMountExplorerMeta,
  type MountExplorerItem,
} from "@/features/mounts/utils/mountExplorerItems";
import {
  itemToMountPreviewFile,
  useMountPreviewSource,
} from "@/features/mounts/components/useMountPreviewSource";
import { createAndCopyMountShareLink } from "@/features/mounts/utils/mountShareLink";
import { useFilesPreviewController } from "@/features/ui/preview/files-preview/useFilesPreviewController";

type MountFilesPreviewProps = {
  currentItem?: MountExplorerItem;
  items: MountExplorerItem[];
  setPreviewCurrentItem?: (item?: MountExplorerItem) => void;
};

const isPreviewableMountItem = (item: MountExplorerItem) => item.type === "file";

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
            rightContent={formatSize(item.size, t)}
          />
        ) : null}
      </div>
    </div>
  );
};

type MountPreviewRightHeaderProps = {
  currentItem?: MountExplorerItem;
};

const MountPreviewRightHeader = ({
  currentItem,
}: MountPreviewRightHeaderProps) => {
  const { t } = useTranslation();

  if (!currentItem?.mountMeta.abilities?.share_link_create) {
    return null;
  }

  return (
    <div className="custom-files-preview-right-header">
      <Button
        variant="tertiary"
        onClick={() => {
          void createAndCopyMountShareLink(currentItem);
        }}
      >
        {t("explorer.rightPanel.share")}
      </Button>
    </div>
  );
};

export const MountFilesPreview = ({
  currentItem,
  items,
  setPreviewCurrentItem,
}: MountFilesPreviewProps) => {
  const { t } = useTranslation();
  const previewSource = useMountPreviewSource();
  const {
    files,
    isOpen,
    openedFileId,
    handleClosePreview,
    handleChangePreviewItem,
  } = useFilesPreviewController({
    currentItem,
    items,
    setPreviewCurrentItem,
    isPreviewableItem: isPreviewableMountItem,
    mapItemToPreviewFile: itemToMountPreviewFile,
  });

  return (
    <FilePreview
      isOpen={isOpen}
      onClose={handleClosePreview}
      title={t("file_preview.title")}
      files={files}
      openedFileId={openedFileId}
      onChangeFile={handleChangePreviewItem}
      headerRightContent={
        <MountPreviewRightHeader currentItem={currentItem} />
      }
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
