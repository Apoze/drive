import type { FileWithPath } from "react-dropzone";
import type { Item } from "@/features/drivers/types";
import type { FileUploadMeta } from "@/features/explorer/components/app-view/AppExplorerInner";

export type ItemUploadFile = FileWithPath & {
  parentId?: string;
};

export type ItemFolderUpload = {
  item: Partial<Item>;
  files: ItemUploadFile[];
  children: ItemFolderUpload[];
  isCurrent?: boolean;
};

export type ItemUploadPlan = {
  folder: ItemFolderUpload;
  type: "folder" | "file";
  files: ItemUploadFile[];
};

/**
 * Removes the leading "./" or "/" from the path.
 */
export const pathNicefy = (path: string) => {
  return path.replace(/^[./]+/, "");
};

export const buildItemUploadPlan = ({
  currentItem,
  files,
}: {
  currentItem: Item;
  files: FileWithPath[];
}): ItemUploadPlan => {
  const folder: ItemFolderUpload = {
    item: currentItem,
    files: [],
    children: [],
    isCurrent: true,
  };

  const findFolder = (folders: ItemFolderUpload[], name: string) => {
    for (const child of folders) {
      if (child.item.title === name) {
        return child;
      }
    }

    return null;
  };

  const getFolder = (folders: ItemFolderUpload[], name: string): ItemFolderUpload => {
    const existingFolder = findFolder(folders, name);
    if (existingFolder) {
      return existingFolder;
    }

    const nextFolder: ItemFolderUpload = {
      item: {
        title: name,
      },
      files: [],
      children: [],
    };
    folders.push(nextFolder);
    return nextFolder;
  };

  const getFolderByPath = (path: string) => {
    const parts = path.split("/").slice(0, -1);

    if (parts.length > 0 && (parts[0] === "" || parts[0] === ".")) {
      parts.shift();
    }

    if (parts.length === 0) {
      return folder;
    }

    let currentFolder = getFolder(folder.children, parts[0]);
    for (let i = 1; i < parts.length; i += 1) {
      currentFolder = getFolder(currentFolder.children, parts[i]);
    }

    return currentFolder;
  };

  for (const file of files) {
    const currentFolder = getFolderByPath(file.path ?? file.name);
    currentFolder.files.push(file as ItemUploadFile);
  }

  return {
    folder,
    type: "folder",
    files: files as ItemUploadFile[],
  };
};

export const buildItemUploadFilesMeta = (files: ItemUploadFile[]) => {
  return files.reduce<Record<string, FileUploadMeta>>((acc, file) => {
    acc[pathNicefy(file.path ?? file.name)] = {
      file,
      progress: 0,
      status: "in_progress",
    };
    return acc;
  }, {});
};
