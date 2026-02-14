import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Button, Modal, ModalSize } from "@gouvfr-lasuite/cunningham-react";
import { DndContext } from "@dnd-kit/core";
import {
  EmbeddedExplorer,
  useEmbeddedExplorer,
} from "@/features/explorer/components/embedded-explorer/EmbeddedExplorer";
import { ItemType } from "@/features/drivers/types";

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

  const explorer = useEmbeddedExplorer({
    initialFolderId,
    isCompact: true,
    gridProps: {
      enableMetaKeySelection: false,
      disableKeyboardNavigation: true,
      disableItemDragAndDrop: true,
      gridActionsCell: () => <div />,
    },
    itemsFilters: { type: ItemType.FOLDER },
  });

  const selectedFolderId = useMemo(() => {
    if (explorer.selectedItems.length === 1) {
      return explorer.selectedItems[0].id;
    }
    return explorer.currentItemId ?? undefined;
  }, [explorer.currentItemId, explorer.selectedItems]);

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
