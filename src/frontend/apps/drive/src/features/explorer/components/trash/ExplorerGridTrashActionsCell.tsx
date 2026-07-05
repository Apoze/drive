import React from "react";
import { errorToString } from "@/features/api/APIError";
import { BatchOperationError } from "@/features/errors/BatchOperationError";
import {
  addToast,
  ToasterItem,
} from "@/features/ui/components/toaster/Toaster";
import {
  useMutationHardDeleteItems,
  useMutationRestoreItems,
} from "@/features/explorer/hooks/useMutations";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { DropdownMenu } from "@gouvfr-lasuite/ui-kit";
import { Button, Decision, useModal } from "@gouvfr-lasuite/cunningham-react";
import undoIcon from "@/assets/icons/undo.svg";
import cancelIcon from "@/assets/icons/cancel.svg";

import { EmbeddedExplorerGridActionsCellProps } from "@/features/explorer/components/embedded-explorer/EmbeddedExplorerGridActionsCell";
import { HardDeleteConfirmationModal } from "@/features/explorer/components/modals/HardDeleteConfirmationModal";

export const ExplorerGridTrashActionsCell = (
  params: EmbeddedExplorerGridActionsCellProps
) => {
  const item = params.row.original;
  const [isOpen, setIsOpen] = useState(false);
  const { t } = useTranslation();
  const restoreItem = useMutationRestoreItems();
  const hardDeleteConfirmationModal = useModal();
  const hardDeleteItem = useMutationHardDeleteItems();

  const handleRestore = async () => {
    try {
      await restoreItem.mutateAsync([item.id]);
      addToast(
        <ToasterItem>
          <span className="material-icons">delete</span>
          <span>{t("explorer.actions.restore.toast", { count: 1 })}</span>
        </ToasterItem>,
      );
    } catch (error) {
      addToast(
        <ToasterItem type="error">
          <span className="material-icons">delete</span>
          <span>
            {error instanceof BatchOperationError
              ? t("explorer.actions.restore.partial_error", {
                  count: error.completedIds.length,
                  name: item.title,
                  detail: errorToString(error.cause),
                })
              : t("explorer.actions.restore.toast_error", { count: 1 })}
          </span>
        </ToasterItem>,
      );
    }
  };

  const handleHardDelete = async (decision: Decision) => {
    if (!decision) {
      return;
    }
    try {
      await hardDeleteItem.mutateAsync([item.id]);
      addToast(
        <ToasterItem>
          <span className="material-icons">delete</span>
          <span>{t("explorer.actions.hard_delete.toast", { count: 1 })}</span>
        </ToasterItem>,
      );
    } catch (error) {
      addToast(
        <ToasterItem type="error">
          <span className="material-icons">delete</span>
          <span>
            {error instanceof BatchOperationError
              ? t("explorer.actions.hard_delete.partial_error", {
                  count: error.completedIds.length,
                  name: item.title,
                  detail: errorToString(error.cause),
                })
              : t("explorer.actions.hard_delete.toast_error", { count: 1 })}
          </span>
        </ToasterItem>,
      );
    }
  };

  return (
    <>
      <DropdownMenu
        options={[
          {
            icon: <img src={undoIcon.src} alt="info" width={24} height={24} />,
            label: t("explorer.grid.actions.restore"),
            value: "restore",
            callback: handleRestore,
          },
          {
            icon: (
              <img src={cancelIcon.src} alt="info" width={24} height={24} />
            ),
            label: t("explorer.grid.actions.hard_delete"),
            value: "hard_delete",
            callback: () => hardDeleteConfirmationModal.open(),
          },
        ]}
        isOpen={isOpen}
        onOpenChange={setIsOpen}
      >
        <Button
          onClick={() => setIsOpen(!isOpen)}
          variant="tertiary"
          className="c__language-picker"
          icon={<span className="material-icons">more_horiz</span>}
        ></Button>
      </DropdownMenu>
      {hardDeleteConfirmationModal.isOpen && (
        <HardDeleteConfirmationModal
          {...hardDeleteConfirmationModal}
          onDecide={handleHardDelete}
          count={1}
        />
      )}
    </>
  );
};
