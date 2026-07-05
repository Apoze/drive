import React from "react";
import { errorToString } from "@/features/api/APIError";
import { BatchOperationError } from "@/features/errors/BatchOperationError";
import { ExplorerGridTrashActionsCell } from "@/features/explorer/components/trash/ExplorerGridTrashActionsCell";
import { TrashBrowseExplorer } from "@/features/explorer/components/trash/TrashBrowseExplorer";
import {
  useMutationHardDeleteItems,
  useMutationRestoreItems,
} from "@/features/explorer/hooks/useMutations";
import { getGlobalExplorerLayout } from "@/features/layouts/components/explorer/ExplorerLayout";
import { addToast } from "@/features/ui/components/toaster/Toaster";
import { ToasterItem } from "@/features/ui/components/toaster/Toaster";
import {
  Button,
  Decision,
  useModal,
  useModals,
} from "@gouvfr-lasuite/cunningham-react";
import { useTranslation } from "react-i18next";
import undoIcon from "@/assets/icons/undo_blue.svg";
import cancelIcon from "@/assets/icons/cancel_blue.svg";
import { useGlobalExplorer } from "@/features/explorer/components/GlobalExplorerContext";
import { HardDeleteConfirmationModal } from "@/features/explorer/components/modals/HardDeleteConfirmationModal";
import { messageModalTrashNavigate } from "@/features/explorer/components/trash/utils";
import { DefaultRoute } from "@/utils/defaultRoutes";
import { useDefaultRoute } from "@/hooks/useDefaultRoute";

export default function TrashPage() {
  const { t } = useTranslation();
  const modals = useModals();

  useDefaultRoute(DefaultRoute.TRASH);

  return (
    <TrashBrowseExplorer
      gridActionsCell={ExplorerGridTrashActionsCell}
      gridHeader={
        <div
          className="explorer__content__breadcrumbs"
          data-testid="trash-page-breadcrumbs"
        >
          <div className="explorer__content__header__title">
            {t("explorer.trash.title")}
          </div>
          <div className="explorer__content__header__description">
            {t("explorer.trash.description")}
          </div>
        </div>
      }
      selectionBarActions={<TrashPageSelectionBarActions />}
      onNavigate={() => {
        messageModalTrashNavigate(modals);
      }}
    />
  );
}

TrashPage.getLayout = getGlobalExplorerLayout;

export const TrashPageSelectionBarActions = () => {
  const { selectedItems, clearSelection, replaceSelection } = useGlobalExplorer();
  const restoreItem = useMutationRestoreItems();
  const hardDeleteConfirmationModal = useModal();
  const hardDeleteItem = useMutationHardDeleteItems();
  const { t } = useTranslation();

  const handleRestore = async () => {
    const itemIds = selectedItems.map((item) => item.id);
    try {
      await restoreItem.mutateAsync(itemIds);
      clearSelection();
      addToast(
        <ToasterItem>
          <span className="material-icons">delete</span>
          <span>
            {t("explorer.actions.restore.toast", {
              count: selectedItems.length,
            })}
          </span>
        </ToasterItem>,
      );
    } catch (error) {
      if (error instanceof BatchOperationError) {
        if (error.completedIds.length > 0) {
          replaceSelection(
            selectedItems.filter(
              (selectedItem) => !error.completedIds.includes(selectedItem.id),
            ),
          );
          addToast(
            <ToasterItem>
              <span className="material-icons">delete</span>
              <span>
                {t("explorer.actions.restore.toast", {
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
              {t("explorer.actions.restore.partial_error", {
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
            {t("explorer.actions.restore.toast_error", {
              count: selectedItems.length,
            })}
          </span>
        </ToasterItem>,
      );
    }
  };

  const handleHardDelete = async (decision: Decision) => {
    if (!decision) {
      return;
    }
    const itemIds = selectedItems.map((item) => item.id);
    try {
      await hardDeleteItem.mutateAsync(itemIds);
      clearSelection();
      addToast(
        <ToasterItem>
          <span className="material-icons">delete</span>
          <span>
            {t("explorer.actions.hard_delete.toast", {
              count: selectedItems.length,
            })}
          </span>
        </ToasterItem>,
      );
    } catch (error) {
      if (error instanceof BatchOperationError) {
        if (error.completedIds.length > 0) {
          replaceSelection(
            selectedItems.filter(
              (selectedItem) => !error.completedIds.includes(selectedItem.id),
            ),
          );
          addToast(
            <ToasterItem>
              <span className="material-icons">delete</span>
              <span>
                {t("explorer.actions.hard_delete.toast", {
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
              {t("explorer.actions.hard_delete.partial_error", {
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
            {t("explorer.actions.hard_delete.toast_error", {
              count: selectedItems.length,
            })}
          </span>
        </ToasterItem>,
      );
    }
  };

  return (
    <>
      <Button
        onClick={handleRestore}
        icon={<img src={undoIcon.src} alt="" width={16} height={16} />}
        variant="tertiary"
        size="small"
        aria-label={t("explorer.grid.actions.restore")}
      />
      <Button
        onClick={() => hardDeleteConfirmationModal.open()}
        icon={<img src={cancelIcon.src} alt="" width={16} height={16} />}
        variant="tertiary"
        size="small"
        aria-label={t("explorer.grid.actions.hard_delete")}
      />
      {hardDeleteConfirmationModal.isOpen && (
        <HardDeleteConfirmationModal
          {...hardDeleteConfirmationModal}
          onDecide={handleHardDelete}
          count={selectedItems.length}
        />
      )}
    </>
  );
};
