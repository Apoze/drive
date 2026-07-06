import React, { useSyncExternalStore } from "react";
import {
  Button,
  Modal,
  ModalProps,
  ModalSize,
} from "@gouvfr-lasuite/cunningham-react";
import { HorizontalSeparator, useResponsive } from "@gouvfr-lasuite/ui-kit";
import { useTranslation } from "react-i18next";
import {
  EmbeddedExplorer,
  useEmbeddedExplorer,
} from "@/features/explorer/components/embedded-explorer/EmbeddedExplorer";
import {
  createFolderTargetEmbeddedExplorerProps,
  resolveCurrentFolderTarget,
} from "./folderTargetModalHelpers";

type ExplorerPickFolderModalProps = Pick<ModalProps, "isOpen" | "onClose"> & {
  initialFolderId?: string;
  onPick: (folderId: string) => void;
  title?: string;
  submitLabel?: string;
};

export const ExplorerPickFolderModal = ({
  initialFolderId,
  onPick,
  title,
  submitLabel,
  ...props
}: ExplorerPickFolderModalProps) => {
  const { t } = useTranslation();
  const { isDesktop } = useResponsive();

  const explorer = useEmbeddedExplorer(
    createFolderTargetEmbeddedExplorerProps({
      initialFolderId,
    }),
  );
  const selectedItems = useSyncExternalStore(
    explorer.selectionStore.subscribe,
    explorer.selectionStore.getSelectedItems,
    explorer.selectionStore.getSelectedItems,
  );
  const pickedId =
    resolveCurrentFolderTarget({
      currentItemId: explorer.currentItemId,
      selectedItems,
    }).folderId ?? null;

  return (
    <Modal
      {...props}
      size={isDesktop ? ModalSize.MEDIUM : ModalSize.FULL}
      title={title || t("explorer.actions.archive.pickFolder.title")}
      rightActions={
        <>
          <Button variant="tertiary" onClick={props.onClose}>
            {t("common.cancel")}
          </Button>
          <Button
            disabled={!pickedId}
            onClick={() => {
              if (!pickedId) return;
              onPick(pickedId);
              props.onClose();
            }}
          >
            {submitLabel || t("explorer.actions.archive.pickFolder.submit")}
          </Button>
        </>
      }
    >
      <div className="noPadding">
        <HorizontalSeparator withPadding={false} />
        <div className="modal__move__explorer">
          <EmbeddedExplorer {...explorer} showSearch={true} />
        </div>
        <HorizontalSeparator />
      </div>
    </Modal>
  );
};
