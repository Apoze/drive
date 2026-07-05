import { MenuItem } from "@gouvfr-lasuite/ui-kit";
import React from "react";

export const buildMountImportMenuItems = ({
  canUploadCurrentFolder,
  canImportFoldersCurrentFolder,
  onImportFiles,
  onImportFolders,
  t,
}: {
  canUploadCurrentFolder: boolean;
  canImportFoldersCurrentFolder: boolean;
  onImportFiles: () => void;
  onImportFolders: () => void;
  t: (key: string) => string;
}): MenuItem[] => {
  const items: MenuItem[] = [];

  if (canUploadCurrentFolder) {
    items.push({
      icon: <span className="material-icons">upload_file</span>,
      label: t("explorer.tree.import.files"),
      callback: onImportFiles,
    });
  }

  if (canImportFoldersCurrentFolder) {
    items.push({
      icon: <span className="material-icons">drive_folder_upload</span>,
      label: t("explorer.tree.import.folders"),
      callback: onImportFolders,
    });
  }

  return items;
};
