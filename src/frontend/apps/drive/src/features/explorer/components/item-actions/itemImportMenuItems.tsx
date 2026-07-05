import React from "react";
import type { MenuItem } from "@gouvfr-lasuite/ui-kit";
import uploadFileSvg from "@/assets/icons/upload_file.svg";
import uploadFolderSvg from "@/assets/icons/upload_folder.svg";

export const ITEM_IMPORT_FILES_INPUT_ID = "import-files";
export const ITEM_IMPORT_FOLDERS_INPUT_ID = "import-folders";

export const triggerItemImportInput = (inputId: string) => {
  (document.getElementById(inputId) as HTMLInputElement | null)?.click();
};

export const buildItemImportMenuItems = ({
  t,
  isHidden = false,
  onImportFiles = () => triggerItemImportInput(ITEM_IMPORT_FILES_INPUT_ID),
  onImportFolders = () => triggerItemImportInput(ITEM_IMPORT_FOLDERS_INPUT_ID),
}: {
  t: (key: string) => string;
  isHidden?: boolean;
  onImportFiles?: () => void;
  onImportFolders?: () => void;
}): MenuItem[] => {
  return [
    {
      icon: <img src={uploadFileSvg.src} alt="" />,
      label: t("explorer.tree.import.files"),
      isHidden,
      callback: onImportFiles,
    },
    {
      icon: <img src={uploadFolderSvg.src} alt="" />,
      label: t("explorer.tree.import.folders"),
      isHidden,
      callback: onImportFolders,
    },
  ];
};
