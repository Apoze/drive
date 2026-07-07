import React from "react";
import { Item, ItemType } from "@/features/drivers/types";
import { FilePreview } from "../files-preview/FilesPreview";
import {
  defaultPreviewSource,
  type FilePreviewType,
} from "../files-preview/previewSource";
import { useTranslation } from "react-i18next";
import { itemToPreviewFile } from "@/features/explorer/utils/utils";
import { useDownloadItem } from "@/features/items/hooks/useDownloadItem";
import { ItemInfo } from "@/features/items/components/ItemInfo";
import { Button, useModal } from "@gouvfr-lasuite/cunningham-react";
import { ItemShareModalLauncher } from "@/features/explorer/components/itemShareModalLauncher";
import { useRefreshItemCache } from "@/features/explorer/hooks/useRefreshItems";
import { useFilesPreviewController } from "../files-preview/useFilesPreviewController";
import { useAuth } from "@/features/auth/Auth";
import { AnonymousCTA } from "@/features/ui/components/anonymous-cta/AnonymousCTA";
import { MyFilesCTA } from "@/features/ui/components/my-files-cta/MyFilesCTA";

export enum CustomFilesPreviewMode {
  DEFAULT = "default",
  CONTEXTUAL = "contextual",
}

type CustomFilesPreviewProps = {
  currentItem?: Item;
  items: Item[];
  setPreviewCurrentItem?: (item?: Item) => void;
  /** Used for optimistic updates only ( when the file is renamed in the preview ) */
  onItemsChange?: (items: Item[]) => void;
  mode?: CustomFilesPreviewMode;
};

const isPreviewableItem = (item: Item) => item.type === ItemType.FILE;

export const CustomFilesPreview = ({
  currentItem,
  items,
  setPreviewCurrentItem,
  onItemsChange,
  mode = CustomFilesPreviewMode.DEFAULT,
}: CustomFilesPreviewProps) => {
  const { t } = useTranslation();

  const { handleDownloadItem } = useDownloadItem();
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
    isPreviewableItem,
    mapItemToPreviewFile: itemToPreviewFile,
  });

  const refreshItemCache = useRefreshItemCache();
  const handleFileRename = (file: FilePreviewType, newName: string) => {
    // Optimistic update of the items in the preview.
    onItemsChange?.(items.map((item) => item.id === file.id ? { ...item, title: newName } : item));
    // Update the item in the explorer if needed.
    refreshItemCache(file.id, { title: newName });
  };

  return (
    <FilePreview
      isOpen={isOpen}
      onClose={handleClosePreview}
      title={t("file_preview.title")}
      files={files}
      onChangeFile={handleChangePreviewItem}
      handleDownloadFile={() => handleDownloadItem(currentItem)}
      openedFileId={openedFileId}
      headerRightContent={
        <CustomFilesPreviewRightHeader
          currentItem={currentItem}
          mode={mode}
        />
      }
      sidebarContent={currentItem && <ItemInfo item={currentItem} />}
      onFileRename={handleFileRename}
      source={defaultPreviewSource}
    />
  );
};

type CustomFilesPreviewRightHeaderProps = {
  currentItem?: Item;
  mode: CustomFilesPreviewMode;
};

const CustomFilesPreviewRightHeader = ({
  currentItem,
  mode,
}: CustomFilesPreviewRightHeaderProps) => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const shareModal = useModal();

  if (!currentItem) {
    return null;
  }

  if (mode === CustomFilesPreviewMode.CONTEXTUAL) {
    return (
      <div className="custom-files-preview-right-header">
        {user ? <MyFilesCTA /> : <AnonymousCTA />}
      </div>
    );
  }

  return (
    <>
      <div className="custom-files-preview-right-header">
        <Button variant="tertiary" onClick={shareModal.open}>
          {t("explorer.rightPanel.share")}
        </Button>
      </div>

      <ItemShareModalLauncher
        isOpen={shareModal.isOpen}
        item={currentItem}
        onClose={shareModal.close}
      />
    </>
  );
};
