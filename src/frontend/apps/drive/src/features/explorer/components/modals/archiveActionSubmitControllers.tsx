import React from "react";
import { errorToString } from "@/features/api/APIError";
import { StartArchiveExtractionPayload } from "@/features/explorer/api/useArchiveExtraction";
import { StartArchiveZipPayload } from "@/features/explorer/api/useArchiveZip";
import {
  ArchiveJobKind,
  showArchiveJobToast,
} from "@/features/explorer/components/toasts/ArchiveJobToast";
import { Item, ItemType } from "@/features/drivers/types";
import { addToast, ToasterItem } from "@/features/ui/components/toaster/Toaster";

type Translate = (key: string, options?: Record<string, unknown>) => string;

type ArchiveJobMutation<TPayload> = {
  mutateAsync: (payload: TPayload) => Promise<{ job_id: string }>;
};

type ArchiveActionErrorToastParams = {
  error: unknown;
  fallbackMessage: string;
  icon: string;
};

const showArchiveActionErrorToast = ({
  error,
  fallbackMessage,
  icon,
}: ArchiveActionErrorToastParams) => {
  addToast(
    <ToasterItem type="error">
      <span className="material-icons">{icon}</span>
      <span>{errorToString(error) || fallbackMessage}</span>
    </ToasterItem>,
  );
};

const showArchiveActionStartedToast = ({
  destinationFolderId,
  jobId,
  kind,
}: {
  destinationFolderId: string;
  jobId: string;
  kind: ArchiveJobKind;
}) => {
  showArchiveJobToast({
    kind,
    jobId,
    destinationFolderId,
  });
};

export const ensureZipSuffix = (name: string) => {
  const trimmed = (name || "").trim();
  if (!trimmed) {
    return "archive.zip";
  }
  return trimmed.toLowerCase().endsWith(".zip") ? trimmed : `${trimmed}.zip`;
};

export const defaultArchiveNameForItems = (items: Item[]) => {
  if (items.length === 1) {
    const item = items[0];
    if (item.type === ItemType.FOLDER) {
      return ensureZipSuffix(item.title);
    }
    const base = (item.filename || item.title || "").replace(/\.[^/.]+$/, "");
    return ensureZipSuffix(base || "archive");
  }
  return "archive.zip";
};

export const createArchiveZipSubmitController = ({
  destinationFolderId,
  itemIds,
  onClose,
  startZip,
  t,
}: {
  destinationFolderId?: string;
  itemIds: string[];
  onClose: () => void;
  startZip: ArchiveJobMutation<StartArchiveZipPayload>;
  t: Translate;
}) => {
  const submitArchiveZip = async (archiveName: string) => {
    if (!destinationFolderId) {
      return;
    }

    try {
      const res = await startZip.mutateAsync({
        item_ids: itemIds,
        destination_folder_id: destinationFolderId,
        archive_name: ensureZipSuffix(archiveName),
      });

      showArchiveActionStartedToast({
        destinationFolderId,
        jobId: res.job_id,
        kind: "zip",
      });
      onClose();
    } catch (error) {
      showArchiveActionErrorToast({
        error,
        fallbackMessage: t("explorer.actions.archive.zip.toast_failed"),
        icon: "archive",
      });
    }
  };

  return {
    submitArchiveZip,
  };
};

export const DEFAULT_UNZIP_COLLISION_POLICY = "rename";
export const DEFAULT_UNZIP_CREATE_ROOT_FOLDER = true;

export const getArchiveFolderName = (
  archiveItem: Pick<Item, "filename" | "title">,
) => {
  const raw = archiveItem.filename || archiveItem.title || "archive.zip";
  const lower = raw.toLowerCase();
  if (lower.endsWith(".zip")) {
    const base = raw.slice(0, -4).trim();
    return base || "archive";
  }
  const base = raw.replace(/\.[^/.]+$/, "").trim();
  return base || "archive";
};

export const createArchiveUnzipSubmitController = ({
  archiveItemId,
  destinationFolderId,
  onClose,
  startExtraction,
  t,
}: {
  archiveItemId: string;
  destinationFolderId?: string;
  onClose: () => void;
  startExtraction: ArchiveJobMutation<StartArchiveExtractionPayload>;
  t: Translate;
}) => {
  const submitArchiveExtraction = async ({
    collisionPolicy,
    createRootFolder,
  }: {
    collisionPolicy: StartArchiveExtractionPayload["collision_policy"];
    createRootFolder: boolean;
  }) => {
    if (!destinationFolderId) {
      return;
    }

    try {
      const res = await startExtraction.mutateAsync({
        item_id: archiveItemId,
        destination_folder_id: destinationFolderId,
        mode: "all",
        collision_policy: collisionPolicy,
        create_root_folder: createRootFolder,
      });

      showArchiveActionStartedToast({
        destinationFolderId,
        jobId: res.job_id,
        kind: "unzip",
      });
      onClose();
    } catch (error) {
      showArchiveActionErrorToast({
        error,
        fallbackMessage: t("explorer.actions.archive.unzip.toast_failed"),
        icon: "unarchive",
      });
    }
  };

  return {
    submitArchiveExtraction,
  };
};
