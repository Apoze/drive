import type { ReactNode } from "react";
import { useState } from "react";

import { IconSize, type MenuItem } from "@gouvfr-lasuite/ui-kit";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { useTranslation } from "react-i18next";

import createFolderSvg from "@/assets/icons/create_folder.svg";
import uploadFileSvg from "@/assets/icons/upload_file.svg";
import uploadFolderSvg from "@/assets/icons/upload_folder.svg";
import { useGlobalExplorer } from "@/features/explorer/components/GlobalExplorerContext";
import { Item, ItemType } from "@/features/drivers/types";

import { ItemIcon } from "../components/icons/ItemIcon";
import { ExplorerCreateFileModal, ExplorerCreateFileType } from "../components/modals/ExplorerCreateFileModal";
import { ExplorerCreateFolderModal } from "../components/modals/ExplorerCreateFolderModal";

type UseCreateMenuItemsProps = {
  includeImport?: boolean;
};

type UseCreateMenuItemsReturn = {
  menuItems: MenuItem[];
  modals: ReactNode;
};

const renderFileIcon = (item: Partial<Item>) => {
  return (
    <div>
      <ItemIcon item={item as Item} size={IconSize.MEDIUM} type="mini" />
    </div>
  );
};

/**
 * Hybrid hook (upstream structure + fork UX):
 * - Provides menu items + renders modals from a single place.
 * - Preserves fork "Plus de formats…" entry by opening the advanced create modal
 *   (ExplorerCreateFileModal with type unset).
 */
export const useCreateMenuItems = (
  { includeImport = false }: UseCreateMenuItemsProps = {},
): UseCreateMenuItemsReturn => {
  const { t } = useTranslation();
  const { item, itemId } = useGlobalExplorer();

  const canCreateChildren = item ? item.abilities?.children_create : true;
  const isHidden = !canCreateChildren;

  const createFolderModal = useModal();
  const createFileModal = useModal();
  const [createFileModalType, setCreateFileModalType] = useState<
    ExplorerCreateFileType | undefined
  >(undefined);

  const openCreateFileModal = (type?: ExplorerCreateFileType) => {
    setCreateFileModalType(type);
    createFileModal.open();
  };

  const items: MenuItem[] = [
    {
      icon: <img src={createFolderSvg.src} alt="" />,
      label: t("explorer.actions.createFolder.modal.title"),
      value: "create-folder",
      isHidden,
      callback: createFolderModal.open,
    },
    { type: "separator" },
  ];

  if (includeImport) {
    items.push(
      {
        icon: <img src={uploadFileSvg.src} alt="" />,
        label: t("explorer.tree.import.files"),
        value: "import-files",
        isHidden,
        callback: () => {
          document.getElementById("import-files")?.click();
        },
      },
      {
        icon: <img src={uploadFolderSvg.src} alt="" />,
        label: t("explorer.tree.import.folders"),
        value: "import-folders",
        isHidden,
        callback: () => {
          document.getElementById("import-folders")?.click();
        },
      },
      { type: "separator" },
    );
  }

  items.push(
    {
      icon: renderFileIcon({
        type: ItemType.FILE,
        filename: "document.odt",
        mimetype: "application/vnd.oasis.opendocument.text",
      }),
      label: t("explorer.tree.create.file.doc"),
      value: "create-doc",
      isHidden,
      callback: () => openCreateFileModal(ExplorerCreateFileType.DOC),
    },
    {
      icon: renderFileIcon({
        type: ItemType.FILE,
        filename: "spreadsheet.ods",
        mimetype: "application/vnd.oasis.opendocument.spreadsheet",
      }),
      label: t("explorer.tree.create.file.calc"),
      value: "create-calc",
      isHidden,
      callback: () => openCreateFileModal(ExplorerCreateFileType.CALC),
    },
    {
      icon: renderFileIcon({
        type: ItemType.FILE,
        filename: "presentation.odp",
        mimetype: "application/vnd.oasis.opendocument.presentation",
      }),
      label: t("explorer.tree.create.file.powerpoint"),
      value: "create-powerpoint",
      isHidden,
      callback: () => openCreateFileModal(ExplorerCreateFileType.POWERPOINT),
    },
    {
      icon: <span className="material-icons">more_horiz</span>,
      label: t("explorer.tree.create.file.more_formats"),
      value: "create-more-formats",
      isHidden,
      callback: () => openCreateFileModal(undefined),
    },
  );

  const modals = (
    <>
      <ExplorerCreateFolderModal {...createFolderModal} parentId={itemId} />
      <ExplorerCreateFileModal
        {...createFileModal}
        parentId={itemId}
        canCreateChildren={canCreateChildren}
        type={createFileModalType}
      />
    </>
  );

  return { menuItems: items, modals };
};
