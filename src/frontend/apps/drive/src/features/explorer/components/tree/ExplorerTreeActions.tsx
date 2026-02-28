import { DropdownMenu, IconSize, useDropdownMenu } from "@gouvfr-lasuite/ui-kit";
import { useGlobalExplorer } from "@/features/explorer/components/GlobalExplorerContext";
import createFolderSvg from "@/assets/icons/create_folder.svg";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { useTranslation } from "react-i18next";
import { ExplorerSearchButton } from "@/features/explorer/components/app-view/ExplorerSearchButton";
import { ItemIcon } from "../icons/ItemIcon";
import { Item, ItemType } from "@/features/drivers/types";
import { ExplorerCreateFileType } from "../modals/ExplorerCreateFileModal";

type ExplorerTreeActionsProps = {
  openCreateFolderModal: () => void;
  openCreateFileModal?: (type?: ExplorerCreateFileType) => void;
};

export const ExplorerTreeActions = ({
  openCreateFolderModal,
  openCreateFileModal,
}: ExplorerTreeActionsProps) => {
  const { t } = useTranslation();
  const { treeIsInitialized, item } = useGlobalExplorer();

  const createMenu = useDropdownMenu();
  const canCreateChildren = item ? item?.abilities?.children_create : true;

  if (!treeIsInitialized) {
    return null;
  }

  const renderFileIcon = (item: Partial<Item>) => {
    return (
      <div>
        <ItemIcon item={item as Item} size={IconSize.MEDIUM} type="mini" />
      </div>
    );
  };

  return (
    <div className="explorer__tree__actions">
      <div className="explorer__tree__actions__left">
        <DropdownMenu
          options={[
            {
              icon: <img src={createFolderSvg.src} alt="" />,
              label: t("explorer.actions.createFolder.modal.title"),
              value: "info",
              isHidden: !canCreateChildren,
              callback: openCreateFolderModal,
            },
            {
              icon: renderFileIcon({
                type: ItemType.FILE,
                filename: "document.odt",
                mimetype: "application/vnd.oasis.opendocument.text",
              }),
              label: t("explorer.tree.create.file.doc"),
              value: "create-doc",
              isHidden: !canCreateChildren || !openCreateFileModal,
              callback: () => openCreateFileModal?.(ExplorerCreateFileType.DOC),
            },
            {
              icon: renderFileIcon({
                type: ItemType.FILE,
                filename: "spreadsheet.ods",
                mimetype: "application/vnd.oasis.opendocument.spreadsheet",
              }),
              label: t("explorer.tree.create.file.calc"),
              value: "create-calc",
              isHidden: !canCreateChildren || !openCreateFileModal,
              callback: () => openCreateFileModal?.(ExplorerCreateFileType.CALC),
            },
            {
              icon: renderFileIcon({
                type: ItemType.FILE,
                filename: "presentation.odp",
                mimetype: "application/vnd.oasis.opendocument.presentation",
              }),
              label: t("explorer.tree.create.file.powerpoint"),
              value: "create-powerpoint",
              isHidden: !canCreateChildren || !openCreateFileModal,
              callback: () =>
                openCreateFileModal?.(ExplorerCreateFileType.POWERPOINT),
            },
            {
              icon: <span className="material-icons">more_horiz</span>,
              label: t("explorer.tree.create.file.more_formats"),
              value: "create-more-formats",
              isHidden: !canCreateChildren || !openCreateFileModal,
              callback: () => openCreateFileModal?.(),
            },
          ]}
          {...createMenu}
          onOpenChange={createMenu.setIsOpen}
        >
          <Button
            icon={<span className="material-icons">add</span>}
            onClick={() => createMenu.setIsOpen(true)}
          >
            {t("explorer.tree.createFolder")}
          </Button>
        </DropdownMenu>
      </div>
      <ExplorerSearchButton keyboardShortcut />
    </div>
  );
};
