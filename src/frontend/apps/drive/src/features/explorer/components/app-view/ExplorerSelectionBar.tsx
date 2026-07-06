import React from "react";
import { Button, useModal } from "@gouvfr-lasuite/cunningham-react";
import { useTranslation } from "react-i18next";
import { useGlobalExplorer } from "@/features/explorer/components/GlobalExplorerContext";
import { useAppExplorer } from "@/features/explorer/components/app-view/AppExplorer";
import { addToast, ToasterItem } from "@/features/ui/components/toaster/Toaster";
import { useMutationDeleteItems } from "@/features/explorer/hooks/useMutations";
import { useEffect } from "react";
import { ExplorerZipItemsModal } from "@/features/explorer/components/modals/ExplorerZipItemsModal";
import {
  canZipSelection,
  showArchiveZipLowRightsToast,
} from "../archiveActionEntrypoints";
import {
  canDeleteItems,
  getDeleteItemIds,
} from "../itemActionCommands";
import { MoveItemsModalLauncher } from "../moveItemsModalLauncher";
import { BatchDeleteError } from "@/features/errors/BatchDeleteError";
import { errorToString } from "@/features/api/APIError";
import {
  useSelectedItems,
  useSetSelectedItems,
} from "@/features/explorer/stores/selectionStore";

export const ExplorerSelectionBar = () => {
  const { t } = useTranslation();
  const { clearRightPanelItem } = useGlobalExplorer();
  const selectedItems = useSelectedItems();
  const setSelectedItems = useSetSelectedItems();
  const { selectionBarActions } = useAppExplorer();

  const handleClearSelection = () => {
    setSelectedItems([]);
    clearRightPanelItem();
  };

  return (
    <div className="explorer__selection-bar">
      <div className="explorer__selection-bar__left">
        <div className="explorer__selection-bar__caption">
          {t("explorer.selectionBar.caption", {
            count: selectedItems.length,
          })}
        </div>
        <div className="explorer__selection-bar__actions">
          {selectionBarActions ? (
            selectionBarActions
          ) : (
            <ExplorerSelectionBarActions />
          )}
        </div>
      </div>
      <div className="explorer__selection-bar__actions">
        <Button
          onClick={handleClearSelection}
          icon={<span className="material-icons">close</span>}
          variant="tertiary"
          size="small"
          aria-label={t("explorer.selectionBar.reset_selection")}
        />
      </div>
    </div>
  );
};

export const ExplorerSelectionBarActions = () => {
  const { t } = useTranslation();
  const {
    replaceSelection,
    closeRightPanelIfIncluded,
    cancelUploadsForDeletedItems,
    item,
  } = useGlobalExplorer();
  const selectedItems = useSelectedItems();
  const setSelectedItems = useSetSelectedItems();
  const moveModal = useModal();
  const zipModal = useModal();

  const deleteItems = useMutationDeleteItems();

  const handleDelete = async () => {
    const itemIds = getDeleteItemIds(selectedItems);

    if (canDeleteItems(selectedItems)) {
      try {
        await deleteItems.mutateAsync(itemIds);
        cancelUploadsForDeletedItems(itemIds);
        closeRightPanelIfIncluded(itemIds);
        setSelectedItems([]);
        addToast(
          <ToasterItem>
            <span className="material-icons">delete</span>
            <span>
              {t("explorer.actions.delete.toast", {
                count: selectedItems.length,
              })}
            </span>
          </ToasterItem>,
        );
      } catch (error) {
        if (error instanceof BatchDeleteError) {
          if (error.completedIds.length > 0) {
            cancelUploadsForDeletedItems(error.completedIds);
            closeRightPanelIfIncluded(error.completedIds);
            replaceSelection(
              selectedItems.filter(
                (selectedItem) => !error.completedIds.includes(selectedItem.id),
              ),
            );
            addToast(
              <ToasterItem>
                <span className="material-icons">delete</span>
                <span>
                  {t("explorer.actions.delete.toast", {
                    count: error.completedIds.length,
                  })}
                </span>
              </ToasterItem>,
            );
          }

          const failedItem = selectedItems.find(
            (selectedItem) => selectedItem.id === error.failedId,
          );
          addToast(
            <ToasterItem type="error">
              <span className="material-icons">delete</span>
              <span>
                {t("explorer.actions.delete.partial_error", {
                  count: error.completedIds.length,
                  name: failedItem?.title ?? "",
                  detail: errorToString(error.cause),
                })}
              </span>
            </ToasterItem>,
          );
          return;
        }

        addToast(
          <ToasterItem type="error">
            <span className="material-icons">delete</span>
            <span>
              {t("explorer.actions.delete.toast_error", {
                count: selectedItems.length,
              })}
            </span>
          </ToasterItem>,
        );
      }
    } else {
      addToast(
        <ToasterItem type="error">
          <span className="material-icons">delete</span>
          <span>{t("explorer.actions.delete.low_rights_toast")}</span>
        </ToasterItem>
      );
    }
  };

  // Add event listener when component mounts and remove when unmounts
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "Backspace") {
        event.preventDefault();
        handleDelete();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [selectedItems]);

  return (
    <>
      <Button
        onClick={() => {
          if (!canZipSelection(selectedItems)) {
            showArchiveZipLowRightsToast(t);
            return;
          }
          zipModal.open();
        }}
        icon={<span className="material-icons">archive</span>}
        variant="tertiary"
        size="small"
        aria-label={t("explorer.selectionBar.compress")}
      >
        {t("explorer.actions.archive.zip.button")}
      </Button>
      {/* <Button
        onClick={handleClearSelection}
        icon={<span className="material-icons">download</span>}
        variant="tertiary"
        size="small"
        aria-label={t("explorer.selectionBar.download")}
      /> */}
      <Button
        onClick={handleDelete}
        icon={<span className="material-icons">delete</span>}
        variant="tertiary"
        size="small"
        aria-label={t("explorer.selectionBar.delete")}
      />
      <Button
        onClick={moveModal.open}
        icon={<span className="material-icons">arrow_forward</span>}
        variant="tertiary"
        size="small"
        aria-label={t("explorer.selectionBar.move")}
      />

      <MoveItemsModalLauncher
        isOpen={moveModal.isOpen}
        itemsToMove={selectedItems}
        onClose={moveModal.close}
        initialFolderId={item?.id}
      />

      {zipModal.isOpen && (
        <ExplorerZipItemsModal
          {...zipModal}
          items={selectedItems}
          initialDestinationFolderId={item?.id}
        />
      )}
    </>
  );
};
