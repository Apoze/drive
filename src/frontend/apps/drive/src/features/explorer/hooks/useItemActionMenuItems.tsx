import { Item, ItemType } from "@/features/drivers/types";
import { useTreeContext, MenuItem } from "@gouvfr-lasuite/ui-kit";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { t } from "i18next";
import React from "react";
import { useGlobalExplorer } from "../components/GlobalExplorerContext";
import settingsSvg from "@/assets/icons/settings.svg";
import starredSvg from "@/assets/icons/starred.svg";
import unstarredSvg from "@/assets/icons/starred-slash.svg";
import { useDownloadItem } from "@/features/items/hooks/useDownloadItem";
import { baseApiUrl } from "@/features/api/utils";
import { ExplorerRenameItemModal } from "../components/modals/ExplorerRenameItemModal";
import { ExplorerUnzipModal } from "../components/modals/ExplorerUnzipModal";
import { ConvertLegacyFileModal } from "../components/modals/ConvertLegacyFileModal";
import { useDeleteItem } from "./useDeleteItem";
import { getParentIdFromPath, setManualNavigationItemId } from "../utils/utils";
import { useRouter } from "next/router";
import { useEffect, useState } from "react";
import {
  useMutationCreateFavoriteItem,
  useMutationDeleteFavoriteItem,
  useMutationDuplicateItem,
} from "./useMutations";
import { DefaultRoute } from "@/utils/defaultRoutes";
import {
  canUnzipItem,
  openArchiveItemModal,
} from "../components/archiveActionEntrypoints";
import { handleFavoriteCommand } from "../components/itemActionCommands";
import { openSingleItemModal } from "../components/itemModalLaunchers";
import { ItemShareModalLauncher } from "../components/itemShareModalLauncher";
import { MoveItemsModalLauncher } from "../components/moveItemsModalLauncher";
import {
  addToast,
  ToasterItem,
} from "@/features/ui/components/toaster/Toaster";

type UseItemActionMenuItemsOptions = {
  onModalOpenChange?: (isModalOpen: boolean) => void;
};

type UseItemActionMenuItemsReturn = {
  getMenuItems: (
    item: Item,
    options?: { minimal?: boolean; itemId?: string },
  ) => MenuItem[];
  modals: React.ReactNode;
  isModalOpen: boolean;
};

export const useItemActionMenuItems = ({
  onModalOpenChange,
}: UseItemActionMenuItemsOptions = {}): UseItemActionMenuItemsReturn => {
  const router = useRouter();
  const { openRightPanelForItem, ...explorerContext } = useGlobalExplorer();
  const { handleDownloadItem } = useDownloadItem();
  const { deleteItems: deleteItem } = useDeleteItem();
  const treeContext = useTreeContext();

  const { mutateAsync: deleteFavoriteItem } = useMutationDeleteFavoriteItem();
  const { mutateAsync: createFavoriteItem } = useMutationCreateFavoriteItem();
  const { mutateAsync: duplicateItem } = useMutationDuplicateItem();

  const shareItemModal = useModal();
  const renameModal = useModal();
  const moveModal = useModal();
  const unzipModal = useModal();
  const convertModal = useModal();

  const [currentItem, setCurrentItem] = useState<Item | null>(null);

  const isModalOpen =
    renameModal.isOpen ||
    shareItemModal.isOpen ||
    moveModal.isOpen ||
    unzipModal.isOpen ||
    convertModal.isOpen;

  useEffect(() => {
    onModalOpenChange?.(isModalOpen);
  }, [isModalOpen]);

  const handleFavorite = async (effectiveItemId: string, item: Item) => {
    await handleFavoriteCommand({
      createFavoriteItem,
      effectiveItemId,
      item,
      addFavoriteChild: (itemTree) => {
        treeContext?.treeData.addChild(DefaultRoute.FAVORITES, itemTree);
      },
    });
  };

  const handleUnfavorite = async (effectiveItemId: string) => {
    await deleteFavoriteItem(effectiveItemId);
  };

  const handleDelete = async (effectiveItemId: string, item: Item) => {
    await deleteItem([effectiveItemId]);
    const currentExplorerItem = explorerContext.item;
    if (!currentExplorerItem) return;

    const parentId = getParentIdFromPath(item.path);
    const redirectId: string | undefined = parentId;

    if (redirectId) {
      setManualNavigationItemId(redirectId);
      router.push(`/explorer/items/${redirectId}`);
    } else {
      router.push(`/explorer/items/my-files`);
    }
  };

  const getMenuItems = (
    item: Item,
    options?: { minimal?: boolean; itemId?: string },
  ): MenuItem[] => {
    const minimal = options?.minimal ?? false;
    const effectiveItemId = options?.itemId ?? item.originalId ?? item.id;
    const effectiveItem = { ...item, id: effectiveItemId };

    return [
      {
        icon: <span className="material-icons">group</span>,
        label: t("explorer.item.actions.share"),
        isHidden: !item.abilities?.accesses_view,
        callback: () => {
          openSingleItemModal({
            item: effectiveItem,
            openModal: shareItemModal.open,
            setCurrentItem,
          });
        },
      },
      {
        icon: <span className="material-icons">download</span>,
        label: t("explorer.item.actions.download"),
        isHidden: item.type === ItemType.FOLDER || minimal || !item.url,
        callback: () => {
          handleDownloadItem(item);
        },
      },
      {
        icon: <span className="material-icons">download</span>,
        label: t("explorer.item.actions.download"),
        isHidden:
          item.type !== ItemType.FOLDER || !item.abilities?.export || minimal,
        callback: () => {
          window.location.href = `${baseApiUrl()}items/${effectiveItemId}/export/`;
        },
      },
      {
        icon: <span className="material-icons">content_copy</span>,
        label: t("explorer.item.actions.duplicate"),
        isHidden:
          item.type === ItemType.FOLDER ||
          minimal ||
          !item.abilities?.duplicate,
        callback: async () => {
          try {
            await duplicateItem(effectiveItemId);
          } catch {
            addToast(
              <ToasterItem>
                {t("explorer.item.actions.duplicate_error")}
              </ToasterItem>,
              {
                type: "error",
              },
            );
          }
        },
      },
      {
        icon: <span className="material-icons">transform</span>,
        label: t("explorer.item.actions.convert"),
        isHidden:
          item.type === ItemType.FOLDER ||
          minimal ||
          !item.abilities?.convert,
        callback: () => {
          setCurrentItem(effectiveItem);
          convertModal.open();
        },
      },
      {
        icon: <span className="material-icons">unarchive</span>,
        label: t("explorer.item.actions.unzip"),
        isHidden: !canUnzipItem(item, { minimal }),
        callback: () => {
          openArchiveItemModal({
            item: effectiveItem,
            openModal: unzipModal.open,
            setCurrentItem,
          });
        },
      },
      { type: "separator" },
      {
        icon: (
          <img
            src={item.is_favorite ? unstarredSvg.src : starredSvg.src}
            alt=""
          />
        ),
        label: item.is_favorite
          ? t("explorer.item.actions.unfavorite")
          : t("explorer.item.actions.favorite"),
        isHidden: !item.abilities?.retrieve,
        callback: item.is_favorite
          ? () => handleUnfavorite(effectiveItemId)
          : () => handleFavorite(effectiveItemId, item),
      },
      { type: "separator" },
      {
        icon: <img src={settingsSvg.src} alt="" />,
        label: t("explorer.item.actions.rename"),
        isHidden: !item.abilities?.update,
        callback: () => {
          setCurrentItem(effectiveItem);
          renameModal.open();
        },
      },
      {
        icon: <span className="material-icons">arrow_forward</span>,
        label: t("explorer.item.actions.move"),
        isHidden: !item.abilities?.move || minimal,
        callback: () => {
          openSingleItemModal({
            item: effectiveItem,
            openModal: moveModal.open,
            setCurrentItem,
          });
        },
      },
      { type: "separator" },
      {
        icon: <span className="material-icons">info</span>,
        label: t("explorer.item.actions.view_info"),
        isHidden: minimal,
        callback: () => {
          openRightPanelForItem(item);
        },
      },
      { type: "separator" },
      {
        icon: <span className="material-icons">delete</span>,
        label: t("explorer.item.actions.delete"),
        variant: "danger" as const,
        isHidden: !item.abilities?.destroy || item.main_workspace || minimal,
        callback: () => handleDelete(effectiveItemId, item),
      },
    ];
  };

  const modals = (
    <>
      {currentItem && renameModal.isOpen && (
        <ExplorerRenameItemModal
          {...renameModal}
          item={currentItem}
          key={currentItem.id}
        />
      )}
      <ItemShareModalLauncher
        isOpen={shareItemModal.isOpen}
        item={currentItem}
        onClose={shareItemModal.close}
        key={currentItem?.id ? `share-${currentItem.id}` : "share-empty"}
      />
      <MoveItemsModalLauncher
        isOpen={moveModal.isOpen}
        itemsToMove={currentItem ? [currentItem] : []}
        onClose={moveModal.close}
        key={currentItem?.id ? `move-${currentItem.id}` : "move-empty"}
        initialFolderId={
          currentItem ? getParentIdFromPath(currentItem.path) : undefined
        }
      />
      {currentItem && unzipModal.isOpen && (
        <ExplorerUnzipModal
          {...unzipModal}
          archiveItem={currentItem}
          initialDestinationFolderId={explorerContext.item?.id}
        />
      )}
      {currentItem && convertModal.isOpen && (
        <ConvertLegacyFileModal
          item={currentItem}
          isOpen={convertModal.isOpen}
          onClose={convertModal.close}
        />
      )}
    </>
  );

  return { getMenuItems, modals, isModalOpen };
};
