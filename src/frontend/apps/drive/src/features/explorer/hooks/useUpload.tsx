import React from "react";
import { useCallback, useEffect } from "react";
import { toast } from "react-toastify";
import { Item } from "@/features/drivers/types";
import { useDropzone } from "react-dropzone";
import { useMutationCreateFolder, useMutationCreateFile } from "./useMutations";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useRef } from "react";
import { Id } from "react-toastify";
import { FileUploadMeta } from "@/features/explorer/components/app-view/AppExplorerInner";
import { ToasterItem } from "@/features/ui/components/toaster/Toaster";
import { addToast } from "@/features/ui/components/toaster/Toaster";
import { FileUploadToast } from "../components/toasts/FileUploadToast";
import { useQueryClient } from "@tanstack/react-query";
import { getEntitlements } from "@/utils/entitlements";
import { useEntitlementsQuery } from "@/features/entitlements/useEntitlementsQuery";
import { useCanCreateChildren } from "@/features/items/utils";
import { getMyFilesQueryKey } from "@/utils/defaultRoutes";
import { UploadError } from "@/features/errors/UploadError";
import { errorToString } from "@/features/api/APIError";
import { getDriver } from "@/features/config/Config";
import { useConfig } from "@/features/config/ConfigProvider";
import {
  formatSize,
  isIdInItemTree,
} from "@/features/explorer/utils/utils";
import {
  buildItemUploadFilesMeta,
  buildItemUploadPlan,
  ItemFolderUpload,
  ItemUploadFile,
  ItemUploadPlan,
  pathNicefy,
} from "./itemUploadPlan";
import {
  customGetFilesFromEvent,
  isEmptyFolderMarker,
} from "@/features/explorer/utils/dropTraversal";
import { useRefreshQueryCacheAfterMutation } from "./useRefreshItems";

type ActiveUpload = {
  file: ItemUploadFile;
  parentPath: string;
  abort?: () => Promise<void> | void;
};

type CreateFolderMutate = (
  variables: { title: string; parentId?: string },
  options: { onSuccess: (createdFolder: Item) => void },
) => void;

type UploadQueryClient = {
  invalidateQueries: (params: { queryKey: unknown[] }) => void;
};

export const createFoldersFromDrop = async ({
  parentItem,
  folderUploads,
  createFolder,
  queryClient,
}: {
  parentItem: Item | undefined;
  folderUploads: ItemFolderUpload[];
  createFolder: CreateFolderMutate;
  queryClient: UploadQueryClient;
}) => {
  const promises = [];

  for (const folder of folderUploads) {
    promises.push(
      () =>
        new Promise<void>((resolve) => {
          createFolder(
            {
              title: folder.item.title!,
              parentId: parentItem?.id,
            },
            {
              onSuccess: async (createdFolder) => {
                queryClient.invalidateQueries({
                  queryKey: getMyFilesQueryKey(),
                });

                if (parentItem) {
                  queryClient.invalidateQueries({
                    queryKey: ["items", parentItem.id],
                  });
                }

                const createdFolderPath =
                  createdFolder.path ??
                  (parentItem?.path
                    ? `${parentItem.path}.${createdFolder.id}`
                    : createdFolder.id);
                folder.files.forEach((file) => {
                  file.parentId = createdFolder.id;
                  file.parentPath = createdFolderPath;
                });
                await createFoldersFromDrop({
                  parentItem: {
                    ...createdFolder,
                    path: createdFolderPath,
                  },
                  folderUploads: folder.children,
                  createFolder,
                  queryClient,
                });
                resolve();
              },
            },
          );
        }),
    );
  }

  for (const promise of promises) {
    await promise();
  }
};

export const handleUploadHierarchy = async ({
  item,
  upload,
  createFolder,
  queryClient,
}: {
  item: Item;
  upload: ItemUploadPlan;
  createFolder: CreateFolderMutate;
  queryClient: UploadQueryClient;
}) => {
  upload.folder.files.forEach((file) => {
    file.parentId = item.id;
    file.parentPath = item.path;
  });
  await createFoldersFromDrop({
    parentItem: item,
    folderUploads: upload.folder.children,
    createFolder,
    queryClient,
  });
};

export const partitionUploadFilesBySize = ({
  files,
  maxSize,
}: {
  files: File[];
  maxSize?: number | null;
}) => {
  if (maxSize === undefined || maxSize === null) {
    return {
      allowedFiles: files,
      tooLargeFiles: [] as File[],
    };
  }

  return {
    allowedFiles: files.filter((file) => file.size <= maxSize),
    tooLargeFiles: files.filter((file) => file.size > maxSize),
  };
};

export const shouldPreventUploadUnload = (step: UploadingStep) => {
  return [UploadingStep.CREATE_FOLDERS, UploadingStep.UPLOAD_FILES].includes(
    step,
  );
};

export const retryUploadFile = async ({
  path,
  meta,
  driver,
  createFile,
  setFileMeta,
}: {
  path: string;
  meta: FileUploadMeta;
  driver: Pick<ReturnType<typeof getDriver>, "reinitiateFileUpload">;
  createFile: Pick<ReturnType<typeof useMutationCreateFile>, "mutate">;
  setFileMeta: (path: string, meta: Partial<FileUploadMeta>) => void;
}) => {
  setFileMeta(path, {
    progress: 0,
    status: "in_progress",
    error: undefined,
  });

  try {
    if (meta.itemId) {
      await driver.reinitiateFileUpload({
        itemId: meta.itemId,
        file: meta.file,
        filename: meta.file.name,
        progressHandler: (progress) => {
          setFileMeta(path, { progress, status: "in_progress" });
        },
      });
    } else {
      await new Promise<void>((resolve, reject) => {
        createFile.mutate(
          {
            filename: meta.file.name,
            file: meta.file,
            parentId: (meta.file as ItemUploadFile).parentId,
            progressHandler: (progress) => {
              setFileMeta(path, { progress, status: "in_progress" });
            },
          },
          {
            onSuccess: () => resolve(),
            onError: (error) => reject(error),
          },
        );
      });
    }

    setFileMeta(path, { progress: 100, status: "done" });
  } catch (error) {
    const nextAction = error instanceof UploadError ? error.nextAction : "retry";
    setFileMeta(path, {
      status: "failed",
      itemId: error instanceof UploadError ? error.itemId : meta.itemId,
      error: {
        message: errorToString(error),
        nextAction,
      },
    });
  }
};

const useUpload = ({ item }: { item: Item }) => {
  const createFolder = useMutationCreateFolder();
  const queryClient = useQueryClient();

  // Assign each file a parentId and create the folders if it is a folder upload.
  const handleHierarchy = async (upload: ItemUploadPlan) => {
    await handleUploadHierarchy({
      item: item!,
      upload,
      createFolder: createFolder.mutate,
      queryClient,
    });
  };

  return {
    handleHierarchy,
  };
};

export enum UploadingStep {
  NONE = "none",
  PREPARING = "preparing",
  CREATE_FOLDERS = "create_folders",
  UPLOAD_FILES = "upload_files",
  DONE = "done",
}

export type UploadingState = {
  step: UploadingStep;
  filesMeta: Record<string, FileUploadMeta>;
};

export const useUploadZone = ({ item }: { item: Item }) => {
  const { t } = useTranslation();
  const { config } = useConfig();

  const createFile = useMutationCreateFile();
  const driver = getDriver();
  const refresh = useRefreshQueryCacheAfterMutation();

  const canCreateChildren = useCanCreateChildren(item);
  const { data: entitlements } = useEntitlementsQuery();
  const canUploadByEntitlements = entitlements?.can_upload?.result ?? true;
  const cannotUploadMessage =
    entitlements?.can_upload?.message || t("entitlements.can_upload.cannot_upload");
  const canUpload = canCreateChildren && canUploadByEntitlements;

  const fileDragToastId = useRef<Id | null>(null);
  const fileUploadsToastId = useRef<Id | null>(null);
  const [uploadingState, setUploadingState] = useState<UploadingState>({
    step: UploadingStep.NONE,
    filesMeta: {},
  });
  const activeUploadsRef = useRef<Map<string, ActiveUpload>>(new Map());
  const isProcessingRef = useRef(false);

  const { handleHierarchy } = useUpload({ item: item! });

  const setFileMeta = useCallback((path: string, meta: Partial<FileUploadMeta>) => {
    setUploadingState((prev) => ({
      ...prev,
      filesMeta: {
        ...prev.filesMeta,
        [path]: {
          ...prev.filesMeta[path],
          ...meta,
        } as FileUploadMeta,
      },
    }));
  }, []);

  const handleRetry = useCallback(async (path: string) => {
    const meta = uploadingState.filesMeta[path];
    if (!meta) {
      return;
    }

    setUploadingState((prev) => ({
      ...prev,
      step: UploadingStep.UPLOAD_FILES,
    }));

    setFileMeta(path, {
      progress: 0,
      status: "in_progress",
      error: undefined,
    });

    await retryUploadFile({
      path,
      meta,
      driver,
      createFile,
      setFileMeta,
    });
  }, [createFile, driver, setFileMeta, uploadingState.filesMeta]);

  const cancelUploadByPath = useCallback(async (path: string) => {
    const activeUpload = activeUploadsRef.current.get(path);
    activeUploadsRef.current.delete(path);
    if (activeUpload?.abort) {
      await activeUpload.abort();
    }

    setFileMeta(path, { status: "cancelled" });
  }, [setFileMeta]);

  const cancelAllUploads = useCallback(() => {
    const activePaths = Array.from(activeUploadsRef.current.keys());
    activePaths.forEach((path) => void cancelUploadByPath(path));
  }, [cancelUploadByPath]);

  const validateDrop = () => {
    if (!canUpload) {
      return {
        code: "no-upload-rights",
        message: canCreateChildren
          ? cannotUploadMessage
          : t("explorer.actions.upload.toast_no_rights"),
      };
    }
    return null;
  };

  const dismissDragToast = () => {
    if (!fileDragToastId.current) {
      return;
    }
    toast.dismiss(fileDragToastId.current);
    fileDragToastId.current = null;
  };

  const dropZone = useDropzone({
    noClick: true,
    useFsAccessApi: false,
    validator: validateDrop,
    getFilesFromEvent: customGetFilesFromEvent,
    // If we do not set this, the click on the "..." menu of each items does not work, also click + select on items
    // does not work too. It might seems related to onFocus and onBlur events.
    noKeyboard: true,
    onDragEnter: () => {
      if (fileDragToastId.current) {
        return;
      }

      fileDragToastId.current = addToast(
        <ToasterItem
          type={canUpload ? "info" : "error"}
          onDrop={dismissDragToast}
        >
          <span className="material-icons">cloud_upload</span>
          <span>
            {t(
              `explorer.actions.upload.toast${canUpload ? "" : "_no_rights"}`,
              {
                title: item?.title,
              },
            )}
          </span>
        </ToasterItem>,
        { autoClose: false },
      );
    },
    onDragLeave: (event) => {
      // Check if we're leaving the dropzone for a toast or staying within the dropzone area
      const relatedTarget = event.relatedTarget as Element;
      const isToastElement = relatedTarget?.closest(".Toastify");

      /*  If we're leaving the dropzone for a toast, we don't need to dismiss the toast.
       *  This is useful to avoid the flicker effect when the user drops a file over the toast.
       *  However, if we drop over a toast, the toast is never closed. This is because we added the onDrop={handleDrop} on the ToasterItem.
       */
      if (isToastElement) {
        return;
      }

      dismissDragToast();
    },
    onDrop: async (acceptedFiles) => {
      if (!canCreateChildren) {
        dismissDragToast();
        return;
      }

      const hasOnlyEmptyFolders =
        acceptedFiles.length > 0 &&
        acceptedFiles.every((file) => isEmptyFolderMarker(file));
      const showFileUploadToast = () => {
        if (hasOnlyEmptyFolders || fileUploadsToastId.current) {
          return;
        }
        fileUploadsToastId.current = addToast(
          <FileUploadToast
            uploadingState={uploadingState}
            onRetry={handleRetry}
            onCancelFile={(path) => void cancelUploadByPath(path)}
            onCancelAll={cancelAllUploads}
          />,
          {
            autoClose: false,
            onClose: () => {
              // We need to set this to null in order to re-show the toast when the user drops another file later.
              fileUploadsToastId.current = null;
            },
          },
        );
      };

      setUploadingState((prev) => ({
        ...prev,
        step: UploadingStep.PREPARING,
      }));

      showFileUploadToast();

      const entitlements = await getEntitlements();
      if (!entitlements.can_upload.result) {
        dismissDragToast();
        setUploadingState((prev) => ({
          ...prev,
          step: UploadingStep.NONE,
        }));
        addToast(
          <ToasterItem type="error">
            <span>
              {entitlements.can_upload.message ||
                t("entitlements.can_upload.cannot_upload")}
            </span>
          </ToasterItem>,
        );
        return;
      }

      const maxSize = config.DATA_UPLOAD_MAX_MEMORY_SIZE;
      const emptyFolderMarkers = acceptedFiles.filter((file) =>
        isEmptyFolderMarker(file),
      );
      const { tooLargeFiles, allowedFiles } = partitionUploadFilesBySize({
        files: acceptedFiles.filter((file) => !isEmptyFolderMarker(file)),
        maxSize,
      });
      if (maxSize !== undefined && maxSize !== null) {
        for (const file of tooLargeFiles) {
          addToast(
            <ToasterItem type="error">
              <span>
                {t("explorer.actions.upload.file_too_large", {
                  name: file.name,
                  maxSize: formatSize(maxSize, t),
                })}
              </span>
            </ToasterItem>,
          );
        }
      }

      const filesForHierarchy = [...allowedFiles, ...emptyFolderMarkers];
      if (filesForHierarchy.length === 0) {
        dismissDragToast();
        setUploadingState((prev) => ({
          ...prev,
          step: UploadingStep.NONE,
        }));
        return;
      }

      setUploadingState((prev) => ({
        ...prev,
        step: UploadingStep.CREATE_FOLDERS,
      }));

      showFileUploadToast();
      dismissDragToast();

      const upload = buildItemUploadPlan({
        currentItem: item!,
        files: filesForHierarchy,
      });
      await handleHierarchy(upload);

      if (hasOnlyEmptyFolders) {
        setUploadingState((prev) => ({
          ...prev,
          step: UploadingStep.DONE,
        }));
        addToast(
          <ToasterItem type="info">
            <span>{t("explorer.actions.upload.folders_created")}</span>
          </ToasterItem>,
        );
        return;
      }

      if (upload.files.length === 0) {
        dismissDragToast();
        setUploadingState((prev) => ({
          ...prev,
          step: UploadingStep.NONE,
        }));
        return;
      }

      const newFilesMeta = buildItemUploadFilesMeta(upload.files);
      if (isProcessingRef.current) {
        setUploadingState((prev) => ({
          step: UploadingStep.UPLOAD_FILES,
          filesMeta: {
            ...prev.filesMeta,
            ...newFilesMeta,
          },
        }));
      } else {
        setUploadingState({
          step: UploadingStep.UPLOAD_FILES,
          filesMeta: newFilesMeta,
        });
      }

      for (const file of upload.files) {
        activeUploadsRef.current.set(pathNicefy(file.path ?? file.name), {
          file,
          parentPath: file.parentPath ?? item.path ?? "",
        });
      }

      if (isProcessingRef.current) {
        return;
      }

      isProcessingRef.current = true;
      while (true) {
        let nextEntry: [string, ActiveUpload] | undefined;
        for (const entry of activeUploadsRef.current.entries()) {
          if (!entry[1].abort) {
            nextEntry = entry;
            break;
          }
        }
        if (!nextEntry) {
          break;
        }

        const [path, activeUpload] = nextEntry;
        const file = activeUpload.file;
        const { promise, abort } = driver.createFile({
          filename: file.name,
          file,
          parentId: file.parentId,
          progressHandler: (progress) => {
            setFileMeta(path, {
              file,
              progress,
              status: progress >= 100 ? "done" : "in_progress",
            });
          },
        });
        activeUpload.abort = abort;

        try {
          await promise;
          if (!activeUploadsRef.current.has(path)) {
            continue;
          }
          activeUploadsRef.current.delete(path);
          refresh(file.parentId);
          setFileMeta(path, {
            file,
            progress: 100,
            status: "done",
          });
        } catch (error) {
          const wasCancelled =
            !activeUploadsRef.current.has(path) ||
            (error instanceof DOMException && error.name === "AbortError");
          activeUploadsRef.current.delete(path);
          if (wasCancelled) {
            setFileMeta(path, { status: "cancelled" });
            continue;
          }

          const nextAction =
            error instanceof UploadError ? error.nextAction : "retry";
          setFileMeta(path, {
            status: "failed",
            itemId: error instanceof UploadError ? error.itemId : undefined,
            error: {
              message: errorToString(error),
              nextAction,
            },
          });
        }
      }
      isProcessingRef.current = false;
      setUploadingState((prev) => ({
        ...prev,
        step: UploadingStep.DONE,
      }));
    },
  });

  useEffect(() => {
    if (fileUploadsToastId.current) {
      const activeFiles = Object.values(uploadingState.filesMeta).filter(
        (meta) => meta.status !== "cancelled",
      );
      // If the uploading state is "upload_files" and there are no files, we dismiss the toast.
      // It can happen if the upload fails for unknown reasons.
      if (
        (uploadingState.step === UploadingStep.UPLOAD_FILES &&
          activeFiles.length === 0) ||
        uploadingState.step === UploadingStep.NONE
      ) {
        toast.dismiss(fileUploadsToastId.current);
        fileUploadsToastId.current = null;
      } else {
        toast.update(fileUploadsToastId.current, {
          render: (
            <FileUploadToast
              uploadingState={uploadingState}
              onRetry={handleRetry}
              onCancelFile={(path) => void cancelUploadByPath(path)}
              onCancelAll={cancelAllUploads}
            />
          ),
        });
      }
    }
  }, [cancelAllUploads, cancelUploadByPath, handleRetry, uploadingState]);

  useEffect(() => {
    const unloadCallback = (event: BeforeUnloadEvent) => {
      if (shouldPreventUploadUnload(uploadingState.step)) {
        event.preventDefault();
      }
      return "";
    };

    window.addEventListener("beforeunload", unloadCallback);
    return () => window.removeEventListener("beforeunload", unloadCallback);
  }, [uploadingState.step]);

  const cancelUploadsForDeletedItems = useCallback(
    (deletedIds: string[]) => {
      if (activeUploadsRef.current.size === 0 || deletedIds.length === 0) {
        return;
      }

      const uploadPathsToCancel: string[] = [];
      for (const [path, activeUpload] of activeUploadsRef.current.entries()) {
        if (
          deletedIds.some((deletedId) =>
            isIdInItemTree(activeUpload.parentPath, deletedId),
          )
        ) {
          uploadPathsToCancel.push(path);
        }
      }

      uploadPathsToCancel.forEach((path) => void cancelUploadByPath(path));
    },
    [cancelUploadByPath],
  );

  return {
    dropZone,
    cancelUploadsForDeletedItems,
  };
};
