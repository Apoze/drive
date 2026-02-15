import { errorToString } from "@/features/api/APIError";
import {
  useStartArchiveExtraction,
} from "@/features/explorer/api/useArchiveExtraction";
import { showArchiveJobToast } from "@/features/explorer/components/toasts/ArchiveJobToast";
import { useItem } from "@/features/explorer/hooks/useQueries";
import { Item } from "@/features/drivers/types";
import { addToast, ToasterItem } from "@/features/ui/components/toaster/Toaster";
import {
  Button,
  Modal,
  ModalProps,
  ModalSize,
  useModal,
} from "@gouvfr-lasuite/cunningham-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { ExplorerPickFolderModal } from "./ExplorerPickFolderModal";

export type UnzipCollisionPolicy = "rename" | "skip" | "overwrite";

export const ExplorerUnzipModal = (
  props: Pick<ModalProps, "isOpen" | "onClose"> & {
    archiveItem: Item;
    initialDestinationFolderId?: string;
  },
) => {
  const { t } = useTranslation();
  const startExtraction = useStartArchiveExtraction();
  const pickFolderModal = useModal();

  const [destinationFolderId, setDestinationFolderId] = useState<string | undefined>(
    props.initialDestinationFolderId,
  );
  const [collisionPolicy, setCollisionPolicy] = useState<UnzipCollisionPolicy>("rename");
  const [extractIntoArchiveFolder, setExtractIntoArchiveFolder] = useState(true);

  useEffect(() => {
    if (!props.isOpen) {
      return;
    }
    setDestinationFolderId(props.initialDestinationFolderId);
    setCollisionPolicy("rename");
    setExtractIntoArchiveFolder(true);
  }, [props.initialDestinationFolderId, props.isOpen]);

  const archiveFolderName = useMemo(() => {
    const raw = props.archiveItem.filename || props.archiveItem.title || "archive.zip";
    const lower = raw.toLowerCase();
    if (lower.endsWith(".zip")) {
      const base = raw.slice(0, -4).trim();
      return base || "archive";
    }
    const base = raw.replace(/\.[^/.]+$/, "").trim();
    return base || "archive";
  }, [props.archiveItem.filename, props.archiveItem.title]);

  const effectiveDestinationId = destinationFolderId;
  const destinationItem = useItem(effectiveDestinationId || "", {
    enabled: !!effectiveDestinationId,
  });

  const destinationLabel = useMemo(() => {
    if (!effectiveDestinationId) {
      return t("explorer.actions.archive.common.destination_unknown");
    }
    return destinationItem.data?.title || t("explorer.actions.archive.common.destination_loading");
  }, [destinationItem.data?.title, effectiveDestinationId, t]);

  const canSubmit =
    Boolean(effectiveDestinationId) && !startExtraction.isPending;

  const handleSubmit = async () => {
    if (!effectiveDestinationId) {
      return;
    }

    try {
      const res = await startExtraction.mutateAsync({
        item_id: props.archiveItem.id,
        destination_folder_id: effectiveDestinationId,
        mode: "all",
        collision_policy: collisionPolicy,
        create_root_folder: extractIntoArchiveFolder,
      });

      showArchiveJobToast({
        kind: "unzip",
        jobId: res.job_id,
        destinationFolderId: effectiveDestinationId,
      });

      props.onClose();
    } catch (e) {
      addToast(
        <ToasterItem type="error">
          <span className="material-icons">unarchive</span>
          <span>
            {errorToString(e) || t("explorer.actions.archive.unzip.toast_failed")}
          </span>
        </ToasterItem>,
      );
    }
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
          {...pickFolderModal}
          initialFolderId={effectiveDestinationId}
          onPick={(folderId) => setDestinationFolderId(folderId)}
        />
      )}
    </>
  );
};
