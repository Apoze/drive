import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Button, Modal, ModalSize } from "@gouvfr-lasuite/cunningham-react";
import { DndContext } from "@dnd-kit/core";
import {
  EmbeddedExplorer,
  useEmbeddedExplorer,
} from "@/features/explorer/components/embedded-explorer/EmbeddedExplorer";
import {
  createFolderTargetEmbeddedExplorerProps,
  resolveCurrentFolderTarget,
} from "@/features/explorer/components/modals/folderTargetModalHelpers";

export const ArchiveExtractionModal = ({
  isOpen,
  onClose,
  initialFolderId,
  onConfirm,
}: {
  isOpen: boolean;
  onClose: () => void;
  initialFolderId?: string;
  onConfirm: (destinationFolderId: string | undefined) => void;
}) => {
  const { t } = useTranslation();

  const explorer = useEmbeddedExplorer(
    createFolderTargetEmbeddedExplorerProps({
      disableItemDragAndDrop: true,
      initialFolderId,
    }),
  );

  const selectedFolderId = useMemo(
    () =>
      resolveCurrentFolderTarget({
        currentItemId: explorer.currentItemId,
        selectedItems: explorer.selectedItems,
      }).folderId,
    [explorer.currentItemId, explorer.selectedItems],
  );

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size={ModalSize.MEDIUM}
      title={t("archive_viewer.extract.modal_title")}
      rightActions={
        <>
          <Button variant="bordered" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button
            onClick={() => onConfirm(selectedFolderId)}
            disabled={!selectedFolderId}
          >
            {t("archive_viewer.extract.confirm")}
          </Button>
        </>
      }
    >
      <div className="mt-s">
        <DndContext>
          <EmbeddedExplorer {...explorer} />
        </DndContext>
      </div>
    </Modal>
  );
};
