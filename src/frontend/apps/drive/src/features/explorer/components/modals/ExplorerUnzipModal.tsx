import React from "react";
import {
  useStartArchiveExtraction,
} from "@/features/explorer/api/useArchiveExtraction";
import { Item } from "@/features/drivers/types";
import {
  Button,
  Modal,
  ModalProps,
  ModalSize,
} from "@gouvfr-lasuite/cunningham-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { ExplorerPickFolderModal } from "./ExplorerPickFolderModal";
import {
  createArchiveUnzipSubmitController,
  DEFAULT_UNZIP_COLLISION_POLICY,
  DEFAULT_UNZIP_CREATE_ROOT_FOLDER,
  getArchiveFolderName,
} from "./archiveActionSubmitControllers";
import { useArchiveDestinationController } from "./useArchiveDestinationController";

export type UnzipCollisionPolicy = "rename" | "skip" | "overwrite";

export const ExplorerUnzipModal = (
  props: Pick<ModalProps, "isOpen" | "onClose"> & {
    archiveItem: Item;
    initialDestinationFolderId?: string;
  },
) => {
  const { t } = useTranslation();
  const startExtraction = useStartArchiveExtraction();
  const destinationController = useArchiveDestinationController({
    initialDestinationFolderId: props.initialDestinationFolderId,
    isOpen: props.isOpen,
  });
  const [collisionPolicy, setCollisionPolicy] = useState<UnzipCollisionPolicy>(
    DEFAULT_UNZIP_COLLISION_POLICY,
  );
  const [extractIntoArchiveFolder, setExtractIntoArchiveFolder] = useState(
    DEFAULT_UNZIP_CREATE_ROOT_FOLDER,
  );

  useEffect(() => {
    if (!props.isOpen) {
      return;
    }
    setCollisionPolicy(DEFAULT_UNZIP_COLLISION_POLICY);
    setExtractIntoArchiveFolder(DEFAULT_UNZIP_CREATE_ROOT_FOLDER);
  }, [props.initialDestinationFolderId, props.isOpen]);

  const archiveFolderName = useMemo(() => {
    return getArchiveFolderName(props.archiveItem);
  }, [props.archiveItem.filename, props.archiveItem.title]);

  const { destinationLabel, effectiveDestinationId, pickFolderModal } =
    destinationController;
  const unzipSubmitController = createArchiveUnzipSubmitController({
    archiveItemId: props.archiveItem.id,
    destinationFolderId: effectiveDestinationId,
    onClose: props.onClose,
    startExtraction,
    t,
  });

  const canSubmit =
    Boolean(effectiveDestinationId) && !startExtraction.isPending;

  const handleSubmit = async () => {
    await unzipSubmitController.submitArchiveExtraction({
      collisionPolicy,
      createRootFolder: extractIntoArchiveFolder,
    });
  };

  return (
    <>
      <Modal
        {...props}
        size={ModalSize.SMALL}
        title={t("explorer.actions.archive.unzip.modal.title")}
        rightActions={
          <>
            <Button variant="bordered" onClick={props.onClose}>
              {t("common.cancel")}
            </Button>
            <Button onClick={handleSubmit} disabled={!canSubmit}>
              {t("explorer.actions.archive.unzip.modal.submit")}
            </Button>
          </>
        }
      >
        <div className="mt-s">
          <div style={{ marginBottom: 8, fontWeight: 600 }}>
            {t("explorer.actions.archive.common.destination_label")}
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <div style={{ flex: 1 }}>{destinationLabel}</div>
            <Button
              size="small"
              variant="tertiary"
              onClick={pickFolderModal.open}
              type="button"
            >
              {t("explorer.actions.archive.common.change_destination")}
            </Button>
          </div>
        </div>

        <div className="mt-s">
          <div style={{ marginBottom: 8, fontWeight: 600 }}>
            {t("explorer.actions.archive.unzip.modal.destination_mode_label")}
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Button
              size="small"
              variant={extractIntoArchiveFolder ? "bordered" : "tertiary"}
              onClick={() => setExtractIntoArchiveFolder(true)}
              type="button"
            >
              {t("explorer.actions.archive.unzip.destination_mode.folder", {
                name: archiveFolderName,
              })}
            </Button>
            <Button
              size="small"
              variant={!extractIntoArchiveFolder ? "bordered" : "tertiary"}
              onClick={() => setExtractIntoArchiveFolder(false)}
              type="button"
            >
              {t("explorer.actions.archive.unzip.destination_mode.root")}
            </Button>
          </div>
        </div>

        <div className="mt-s">
          <div style={{ marginBottom: 8, fontWeight: 600 }}>
            {t("explorer.actions.archive.unzip.modal.collision_label")}
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {(["rename", "skip", "overwrite"] as const).map((policy) => (
              <Button
                key={policy}
                size="small"
                variant={collisionPolicy === policy ? "bordered" : "tertiary"}
                onClick={() => setCollisionPolicy(policy)}
                type="button"
              >
                {t(`explorer.actions.archive.unzip.collisions.${policy}`)}
              </Button>
            ))}
          </div>
        </div>
      </Modal>

      {pickFolderModal.isOpen && (
        <ExplorerPickFolderModal
          {...destinationController.pickFolderModalProps}
        />
      )}
    </>
  );
};
