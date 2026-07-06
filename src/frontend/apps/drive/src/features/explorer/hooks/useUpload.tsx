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
import { formatSize } from "@/features/explorer/utils/utils";
import {
  buildItemUploadFilesMeta,
  buildItemUploadPlan,
  ItemFolderUpload,
  ItemUploadFile,
  ItemUploadPlan,
  pathNicefy,
} from "./itemUploadPlan";

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

                folder.files.forEach((file) => {
                  file.parentId = createdFolder.id;
                });
                await createFoldersFromDrop({
                  parentItem: createdFolder,
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

      setUploadingState((prev) => ({
        ...prev,
        step: UploadingStep.PREPARING,
      }));

      if (!fileUploadsToastId.current) {
        fileUploadsToastId.current = addToast(
          <FileUploadToast
            uploadingState={uploadingState}
            onRetry={handleRetry}
          />,
          {
            autoClose: false,
            onClose: () => {
              // We need to set this to null in order to re-show the toast when the user drops another file later.
              fileUploadsToastId.current = null;
            },
          },
        );
      }

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

      // maxSize is undefined when DATA_UPLOAD_MAX_MEMORY_SIZE is not configured,
      // in that case we keep the current behavior.
      const maxSize = config.DATA_UPLOAD_MAX_MEMORY_SIZE;
      const { tooLargeFiles, allowedFiles } = partitionUploadFilesBySize({
        files: acceptedFiles,
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
      if (allowedFiles.length === 0) {
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

      if (!fileUploadsToastId.current) {
        fileUploadsToastId.current = addToast(
          <FileUploadToast
            uploadingState={uploadingState}
            onRetry={handleRetry}
          />,
          {
            autoClose: false,
            onClose: () => {
              // We need to set this to null in order to re-show the toast when the user drops another file later.
              fileUploadsToastId.current = null;
            },
          },
        );
      }
      dismissDragToast();

      const upload = buildItemUploadPlan({
        currentItem: item!,
        files: allowedFiles,
      });
      await handleHierarchy(upload);

      // Do not run "setUploadingState({});" because if a uploading is still in progress, it will be overwritten.

      // First, add all the files to the uploading state in order to display them in the toast.
      const newUploadingState: UploadingState = {
        step: UploadingStep.UPLOAD_FILES,
        filesMeta: buildItemUploadFilesMeta(upload.files),
      };
      setUploadingState(newUploadingState);

      // Then, upload all the files sequentially. We are not uploading them in parallel because the backend
      // does not support it, it causes concurrency issues.
      const promises = [];
      for (const file of upload.files) {
        // We do not using "createFile.mutateAsync" because it causes unhandled errors.
        // Instead, we use a promise that we can await to run all the uploads sequentially.
        // Using "createFile.mutate" makes the error handled by the mutation hook itself.
        promises.push(
          () =>
            new Promise<void>((resolve) => {
              createFile.mutate(
                {
                  filename: file.name,
                  file,
                  parentId: file.parentId,
                  progressHandler: (progress) => {
                    setFileMeta(pathNicefy(file.path!), {
                      file,
                      progress,
                      status: "in_progress",
                    });
                  },
                },
                {
                  onError: (error) => {
                    const nextAction =
                      error instanceof UploadError ? error.nextAction : "retry";
                    setFileMeta(pathNicefy(file.path!), {
                      status: "failed",
                      itemId: error instanceof UploadError ? error.itemId : undefined,
                      error: {
                        message: errorToString(error),
                        nextAction,
                      },
                    });
                  },
                  onSettled: () => {
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
      setUploadingState((prev) => ({
        ...prev,
        step: UploadingStep.DONE,
      }));
    },
  });

  useEffect(() => {
    if (fileUploadsToastId.current) {
      // If the uploading state is "upload_files" and there are no files, we dismiss the toast.
      // It can happen if the upload fails for unknown reasons.
      if (
        (uploadingState.step === UploadingStep.UPLOAD_FILES &&
          Object.keys(uploadingState.filesMeta).length === 0) ||
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
            />
          ),
        });
      }
    }
  }, [handleRetry, uploadingState]);

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

  return {
    dropZone,
  };
};
