import { MountBrowseResponse } from "@/features/drivers/types";
import { errorToString } from "@/features/api/APIError";
import { getDriver } from "@/features/config/Config";
import { FileUploadToast } from "@/features/explorer/components/toasts/FileUploadToast";
import {
  UploadingState,
  UploadingStep,
} from "@/features/explorer/hooks/useUpload";
import { addToast, ToasterItem } from "@/features/ui/components/toaster/Toaster";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { FileWithPath, useDropzone } from "react-dropzone";
import { Id, toast } from "react-toastify";
import { buildMountImportMenuItems } from "./mountImportMenuItems";
import {
  buildMountUploadPlan,
  buildMountUploadProgressFiles,
  classifyMountUploadError,
  MountUploadErrorContext,
  MountUploadPlan,
} from "@/features/mounts/utils/mountUpload";

export const MOUNT_IMPORT_FILES_INPUT_ID = "mount-import-files";
export const MOUNT_IMPORT_FOLDERS_INPUT_ID = "mount-import-folders";

const HIDDEN_INPUT_STYLE = {
  border: 0,
  clip: "rect(0, 0, 0, 0)",
  clipPath: "inset(50%)",
  height: "1px",
  left: 0,
  margin: 0,
  overflow: "hidden",
  padding: 0,
  position: "fixed",
  top: 0,
  whiteSpace: "nowrap",
  width: "1px",
} as const;

type MountUploadSource = File & Pick<Partial<FileWithPath>, "path">;

type MountRetryState = {
  plan: MountUploadPlan<MountUploadSource>;
  createdFolderCount: number;
  uploadedFileCount: number;
  failedFileIndex: number;
};

export const useMountUploadController = ({
  mountId,
  browse,
  canUploadCurrentFolder,
  canImportFoldersCurrentFolder,
  onBrowseRefetch,
}: {
  mountId: string;
  browse?: MountBrowseResponse;
  canUploadCurrentFolder: boolean;
  canImportFoldersCurrentFolder: boolean;
  onBrowseRefetch: () => Promise<unknown> | void;
}) => {
  const { t } = useTranslation();
  const [uploadLoading, setUploadLoading] = useState(false);
  const mountUploadToastId = useRef<Id | null>(null);
  const mountRetryStateRef = useRef<MountRetryState | null>(null);
  const [mountUploadingState, setMountUploadingState] = useState<UploadingState>({
    step: UploadingStep.NONE,
    filesMeta: {},
  });

  const triggerMountImport = useCallback((inputId: string) => {
    (document.getElementById(inputId) as HTMLInputElement | null)?.click();
  }, []);

  const resetMountImportInputs = useCallback(() => {
    [MOUNT_IMPORT_FILES_INPUT_ID, MOUNT_IMPORT_FOLDERS_INPUT_ID].forEach((inputId) => {
      const input = document.getElementById(inputId) as HTMLInputElement | null;
      if (input) {
        input.value = "";
      }
    });
  }, []);

  const setMountUploadFileMeta = useCallback((
    relativePath: string,
    meta: Partial<UploadingState["filesMeta"][string]>,
  ) => {
    setMountUploadingState((prev) => ({
      ...prev,
      filesMeta: {
        ...prev.filesMeta,
        [relativePath]: {
          ...prev.filesMeta[relativePath],
          ...meta,
        },
      },
    }));
  }, []);

  const getMountUploadErrorDetail = useCallback(
    (failedTask: MountUploadErrorContext | null, error: unknown) => {
      if (!failedTask) {
        return errorToString(error);
      }

      const classified = classifyMountUploadError(failedTask);

      if (classified.kind === "folder_conflict_with_file") {
        return t("explorer.mounts.upload.conflict_folder_blocked_by_file", {
          path: classified.relativePath,
        });
      }

      if (classified.kind === "file_already_exists") {
        return t("explorer.mounts.upload.conflict_file_already_exists", {
          path: classified.relativePath,
        });
      }

      return errorToString(error);
    },
    [t],
  );

  const showMountUploadFailureToast = useCallback(
    (params: {
      createdFolderCount: number;
      uploadedFileCount: number;
      failedTask: MountUploadErrorContext | null;
      error: unknown;
    }) => {
      const detail = getMountUploadErrorDetail(params.failedTask, params.error);
      const hasPartialProgress =
        params.createdFolderCount > 0 || params.uploadedFileCount > 0;

      addToast(
        <ToasterItem type="error">
          {hasPartialProgress
            ? t("explorer.mounts.upload.partial_error", {
                folders: params.createdFolderCount,
                files: params.uploadedFileCount,
                detail,
              })
            : detail}
        </ToasterItem>,
      );
    },
    [getMountUploadErrorDetail, t],
  );

  const runMountUpload = useCallback(
    async (params: {
      plan: MountUploadPlan<MountUploadSource>;
      startFileIndex: number;
      createdFolderCount: number;
      uploadedFileCount: number;
      rerunFolders: boolean;
    }) => {
      setUploadLoading(true);
      let keepToastOpen = false;
      let createdFolderCount = params.createdFolderCount;
      let uploadedFileCount = params.uploadedFileCount;
      let firstError: unknown;
      let failedTask: MountUploadErrorContext | null = null;

      try {
        if (params.rerunFolders) {
          setMountUploadingState({
            step: UploadingStep.PREPARING,
            filesMeta: {},
          });
          setMountUploadingState((prev) => ({
            ...prev,
            step: UploadingStep.CREATE_FOLDERS,
          }));

          for (const folderTask of params.plan.folderTasks) {
            try {
              await getDriver().createMountFolder({
                mountId,
                path: folderTask.parentPath,
                name: folderTask.name,
                reuseExisting: true,
              });
              createdFolderCount += 1;
            } catch (error) {
              firstError ??= error;
              failedTask ??= {
                taskType: "folder",
                relativePath: folderTask.relativePath,
                error,
              };
              break;
            }
          }
        }

        if (!firstError) {
          setMountUploadingState({
            step: UploadingStep.UPLOAD_FILES,
            filesMeta: buildMountUploadProgressFiles({
              fileTasks: params.plan.fileTasks,
              completedFileCount: uploadedFileCount,
            }),
          });

          for (
            let fileIndex = params.startFileIndex;
            fileIndex < params.plan.fileTasks.length;
            fileIndex += 1
          ) {
            const fileTask = params.plan.fileTasks[fileIndex];

            try {
              await getDriver().uploadMountFile({
                mountId,
                path: fileTask.parentPath,
                file: fileTask.file,
                progressHandler: (progress) => {
                  setMountUploadFileMeta(fileTask.relativePath, {
                    file: fileTask.file,
                    progress,
                    status: "in_progress",
                  });
                },
              });
              setMountUploadFileMeta(fileTask.relativePath, {
                file: fileTask.file,
                progress: 100,
                status: "done",
              });
              uploadedFileCount += 1;
            } catch (error) {
              failedTask = {
                taskType: "file",
                relativePath: fileTask.relativePath,
                error,
              };
              const classified = classifyMountUploadError(failedTask);

              if (classified.kind === "other") {
                mountRetryStateRef.current = {
                  plan: params.plan,
                  createdFolderCount,
                  uploadedFileCount,
                  failedFileIndex: fileIndex,
                };
                keepToastOpen = true;
                setMountUploadFileMeta(fileTask.relativePath, {
                  file: fileTask.file,
                  progress: 0,
                  status: "failed",
                  error: {
                    message: errorToString(error),
                    nextAction: "retry",
                  },
                });
                break;
              }

              firstError ??= error;
              setMountUploadFileMeta(fileTask.relativePath, {
                file: fileTask.file,
                progress: 0,
                status: "failed",
                error: {
                  message: errorToString(error),
                  nextAction: "contact_admin",
                },
              });
              break;
            }
          }
        }

        if (
          createdFolderCount > params.createdFolderCount ||
          uploadedFileCount > params.uploadedFileCount
        ) {
          await onBrowseRefetch();
        }

        if (keepToastOpen) {
          return;
        }

        mountRetryStateRef.current = null;
        if (firstError) {
          showMountUploadFailureToast({
            createdFolderCount,
            uploadedFileCount,
            failedTask,
            error: firstError,
          });
          return;
        }

        addToast(<ToasterItem>{t("explorer.mounts.upload.success")}</ToasterItem>);
      } finally {
        if (!keepToastOpen) {
          setMountUploadingState({
            step: UploadingStep.NONE,
            filesMeta: {},
          });
        }
        setUploadLoading(false);
        resetMountImportInputs();
      }
    },
    [
      mountId,
      onBrowseRefetch,
      resetMountImportInputs,
      setMountUploadFileMeta,
      showMountUploadFailureToast,
      t,
    ],
  );

  const handleRetryMountUpload = useCallback(
    (relativePath: string) => {
      if (uploadLoading) {
        return;
      }

      const retryState = mountRetryStateRef.current;
      if (!retryState) {
        return;
      }

      const failedFile = retryState.plan.fileTasks[retryState.failedFileIndex];
      if (!failedFile || failedFile.relativePath !== relativePath) {
        return;
      }

      void runMountUpload({
        plan: retryState.plan,
        startFileIndex: retryState.failedFileIndex,
        createdFolderCount: retryState.createdFolderCount,
        uploadedFileCount: retryState.uploadedFileCount,
        rerunFolders: false,
      });
    },
    [runMountUpload, uploadLoading],
  );

  const handleUpload = useCallback(async (files: MountUploadSource[]) => {
    if (!browse || browse.entry.entry_type !== "folder" || files.length === 0) {
      return;
    }

    const uploadPlan = buildMountUploadPlan({
      currentPath: browse.normalized_path,
      files,
    });

    if (uploadPlan.folderTasks.length > 0 && !canImportFoldersCurrentFolder) {
      addToast(
        <ToasterItem type="error">
          {t("explorer.mounts.upload.folders_require_create_folder")}
        </ToasterItem>,
      );
      resetMountImportInputs();
      return;
    }

    mountRetryStateRef.current = null;
    await runMountUpload({
      plan: uploadPlan,
      startFileIndex: 0,
      createdFolderCount: 0,
      uploadedFileCount: 0,
      rerunFolders: true,
    });
  }, [
    browse,
    canImportFoldersCurrentFolder,
    resetMountImportInputs,
    runMountUpload,
    t,
  ]);

  useEffect(() => {
    const activeSteps = [
      UploadingStep.PREPARING,
      UploadingStep.CREATE_FOLDERS,
      UploadingStep.UPLOAD_FILES,
    ];
    const shouldShowToast = activeSteps.includes(mountUploadingState.step);

    if (!shouldShowToast) {
      if (mountUploadToastId.current) {
        toast.dismiss(mountUploadToastId.current);
        mountUploadToastId.current = null;
      }
      return;
    }

    const content = (
      <FileUploadToast
        uploadingState={mountUploadingState}
        onRetry={handleRetryMountUpload}
      />
    );
    if (!mountUploadToastId.current) {
      mountUploadToastId.current = addToast(content, {
        autoClose: false,
        onClose: () => {
          mountUploadToastId.current = null;
        },
      });
      return;
    }

    toast.update(mountUploadToastId.current, {
      render: content,
    });
  }, [handleRetryMountUpload, mountUploadingState]);

  const mountDropZone = useDropzone({
    noClick: true,
    noKeyboard: true,
    useFsAccessApi: false,
    disabled: !canUploadCurrentFolder || uploadLoading,
    onDrop: (acceptedFiles) => {
      if (acceptedFiles.length === 0) {
        return;
      }
      void handleUpload(acceptedFiles as MountUploadSource[]);
    },
  });

  const importFiles = useCallback(() => {
    triggerMountImport(MOUNT_IMPORT_FILES_INPUT_ID);
  }, [triggerMountImport]);

  const importFolders = useCallback(() => {
    triggerMountImport(MOUNT_IMPORT_FOLDERS_INPUT_ID);
  }, [triggerMountImport]);

  const importMenuItems = buildMountImportMenuItems({
    canUploadCurrentFolder,
    canImportFoldersCurrentFolder,
    onImportFiles: importFiles,
    onImportFolders: importFolders,
    t,
  });

  const mountImportInputs = (
    <>
      <input
        {...mountDropZone.getInputProps({
          id: MOUNT_IMPORT_FOLDERS_INPUT_ID,
          webkitdirectory: "true",
          style: HIDDEN_INPUT_STYLE,
        })}
      />
      <input
        {...mountDropZone.getInputProps({
          id: MOUNT_IMPORT_FILES_INPUT_ID,
          style: HIDDEN_INPUT_STYLE,
        })}
      />
    </>
  );

  return {
    uploadLoading,
    mountDropZone,
    mountImportInputs,
    importMenuItems,
  };
};
