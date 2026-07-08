import React from "react";
import { ToasterItem } from "@/features/ui/components/toaster/Toaster";
import { Button, Tooltip } from "@gouvfr-lasuite/cunningham-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import clsx from "clsx";
import { CircularProgress } from "@/features/ui/components/circular-progress/CircularProgress";
import prettyBytes from "pretty-bytes";
import { ToastContentProps } from "react-toastify";
import { getIconByMimeType } from "../icons/ItemIcon";
import type { FileUploadMeta } from "@/features/explorer/components/app-view/AppExplorerInner";
import type { UploadingState } from "@/features/explorer/hooks/useUpload";
import { Spinner } from "@gouvfr-lasuite/ui-kit";
import { useConfig } from "@/features/config/ConfigProvider";
import { getOperationTimeBound } from "@/features/operations/timeBounds";
import { useTimeBoundedPhase } from "@/features/operations/useTimeBoundedPhase";
import { CancelUploadConfirmationModal } from "@/features/explorer/components/modals/CancelUploadConfirmationModal";
import { CheckIcon } from "@/features/ui/components/icon/CheckIcon";
import { ErrorIcon } from "@/features/ui/components/icon/ErrorIcon";

const sortUploadEntries = (
  entries: [string, FileUploadMeta][],
): [string, FileUploadMeta][] => {
  const order: Record<string, number> = {
    in_progress: 0,
    done: 1,
    failed: 2,
    cancelled: 3,
  };

  return [...entries].sort(
    (a, b) => (order[a[1].status ?? "in_progress"] ?? 9) -
      (order[b[1].status ?? "in_progress"] ?? 9),
  );
};

const FileUploadRow = ({
  name,
  meta,
  onRetry,
  onCancelFile,
}: {
  name: string;
  meta: FileUploadMeta;
  onRetry?: (path: string) => void;
  onCancelFile?: (path: string) => void;
}) => {
  const { t } = useTranslation();
  const [hovered, setHovered] = useState(false);
  const icon = getIconByMimeType(meta.file.type, "normal", meta.file.name);
  const canCancel = meta.status === "in_progress" && !!onCancelFile;

  return (
    <div
      key={name}
      className={clsx("file-upload-toast__files__item", {
        "file-upload-toast__files__item--failed": meta.status === "failed",
      })}
    >
      <div className="file-upload-toast__files__item__name">
        <img src={icon.src} alt={name} />
        <span>{name}</span>
        {meta.status !== "failed" && (
          <span className="file-upload-toast__files__item__size">
            {prettyBytes(meta.file.size)}
          </span>
        )}
      </div>
      <div className="file-upload-toast__files__item__progress">
        {meta.status === "done" || meta.progress >= 100 ? (
          <div className="file-upload-toast__files__item__check">
            <CheckIcon />
          </div>
        ) : meta.status === "failed" ? (
          onRetry ? (
            <Tooltip
              content={
                meta.error?.message ?? t("explorer.actions.upload.files.error")
              }
            >
              <Button
                variant="secondary"
                size="small"
                onClick={() => onRetry(name)}
              >
                {t(
                  `explorer.actions.upload.actions.${meta.error?.nextAction ?? "retry"}`,
                )}
              </Button>
            </Tooltip>
          ) : (
            <Tooltip
              content={
                meta.error?.message ?? t("explorer.actions.upload.files.error")
              }
            >
              <div className="file-upload-toast__files__item__error-icon">
                <ErrorIcon size={20} />
              </div>
            </Tooltip>
          )
        ) : canCancel ? (
          <div
            role="button"
            tabIndex={0}
            className="file-upload-toast__files__item__progress--hoverable"
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            onClick={() => onCancelFile?.(name)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onCancelFile?.(name);
              }
            }}
            aria-label={t("explorer.actions.upload.cancel_file", {
              name,
            })}
          >
            <CircularProgress progress={meta.progress} />
            {hovered && (
              <div className="file-upload-toast__files__item__cancel-overlay">
                <span className="material-icons file-upload-toast__files__item__cancel-icon">
                  close
                </span>
              </div>
            )}
          </div>
        ) : (
          <CircularProgress progress={meta.progress} />
        )}
      </div>
    </div>
  );
};

export const FileUploadToast = (
  props: {
    uploadingState: UploadingState;
    onRetry?: (path: string) => void;
    onCancelFile?: (path: string) => void;
    onCancelAll?: () => void;
  } & Partial<ToastContentProps>
) => {
  const { t } = useTranslation();
  const { config } = useConfig();
  const [isOpen, setIsOpen] = useState(true);
  const [isCancelModalOpen, setIsCancelModalOpen] = useState(false);
  const metas = Object.values(props.uploadingState.filesMeta).filter(
    (meta) => meta.status !== "cancelled",
  );
  const inProgressFilesCount = metas.filter((meta) => {
    const status = meta.status ?? "in_progress";
    return status !== "failed" && status !== "done" && meta.progress < 100;
  }).length;
  const doneFilesCount = metas.filter((meta) => {
    const status = meta.status ?? "in_progress";
    return status !== "failed" && (status === "done" || meta.progress >= 100);
  }).length;
  const failedFilesCount = metas.filter((meta) => meta.status === "failed").length;
  const overallProgress =
    metas.length > 0
      ? Math.floor(
          metas.reduce((sum, meta) => sum + meta.progress, 0) / metas.length,
        )
      : 0;
  // Does not show the files list and the open button.
  const simpleMode =
    props.uploadingState.step === "preparing" ||
    props.uploadingState.step === "create_folders";

  const simpleModeBounds = useMemo(
    () => getOperationTimeBound("upload_create", config),
    [config],
  );
  const simpleModePhase = useTimeBoundedPhase(simpleMode, simpleModeBounds);

  useEffect(() => {
    if (props.uploadingState.step === "upload_files") {
      setIsOpen(true);
    }
  }, [props.uploadingState.step]);

  useEffect(() => {
    if (inProgressFilesCount === 0) {
      setIsOpen(failedFilesCount > 0);
    }
  }, [failedFilesCount, inProgressFilesCount]);

  const sortedEntries = sortUploadEntries(
    Object.entries(props.uploadingState.filesMeta),
  );
  const canClose = inProgressFilesCount === 0;

  return (
    <ToasterItem className="file-upload-toast__item">
      <div className="file-upload-toast">
        <div
          className={clsx("file-upload-toast__files", {
            "file-upload-toast__files--closed": !isOpen,
          })}
        >
          {sortedEntries
            .filter(([, meta]) => meta.status !== "cancelled")
            .map(([name, meta]) => (
              <FileUploadRow
                key={name}
                name={name}
                meta={meta}
                onRetry={props.onRetry}
                onCancelFile={props.onCancelFile}
              />
            ))}
        </div>
        <div className="file-upload-toast__description">
          <div className="file-upload-toast__description__text">
            {simpleMode ? (
              <>
                <Spinner />
                {t(
                  `explorer.actions.upload.steps.${props.uploadingState.step}`
                )}
                {simpleModePhase === "still_working" && (
                  <span> {t("operations.long_running.still_working")}</span>
                )}
                {simpleModePhase === "failed" && (
                  <span> {t("operations.long_running.failed")}</span>
                )}
              </>
            ) : (
              <>
                {inProgressFilesCount > 0
                  ? t("explorer.actions.upload.files.description", {
                      count: inProgressFilesCount,
                    })
                  : failedFilesCount > 0 && doneFilesCount > 0
                    ? t("explorer.actions.upload.files.description_done", {
                        count: doneFilesCount,
                      })
                  : failedFilesCount > 0
                    ? t("explorer.actions.upload.files.description_failed", {
                        count: failedFilesCount,
                      })
                    : doneFilesCount > 0
                      ? t("explorer.actions.upload.files.description_done", {
                          count: doneFilesCount,
                        })
                      : null}
                {inProgressFilesCount > 0 && (
                  <span className="file-upload-toast__description__percentage">
                    {overallProgress}%
                  </span>
                )}
                {failedFilesCount > 0 && (
                  <Tooltip
                    content={t("explorer.actions.upload.files.description_failed", {
                      count: failedFilesCount,
                    })}
                  >
                    <span className="file-upload-toast__description__error-indicator">
                      <ErrorIcon size={20} />
                    </span>
                  </Tooltip>
                )}
              </>
            )}
          </div>
          <div className="file-upload-toast__description__actions">
            {!simpleMode && (
              <Button
                variant="tertiary"
                size="small"
                icon={
                  <span className="material-icons">
                    {isOpen ? "keyboard_arrow_up" : "keyboard_arrow_down"}
                  </span>
                }
                onClick={() => setIsOpen(!isOpen)}
              ></Button>
            )}

            <Button
              onClick={
                canClose || !props.onCancelAll
                  ? props.closeToast
                  : () => setIsCancelModalOpen(true)
              }
              disabled={!canClose && !props.onCancelAll}
              variant="tertiary"
              size="small"
              icon={<span className="material-icons">close</span>}
            ></Button>
          </div>
        </div>
      </div>
      {props.onCancelAll && (
        <CancelUploadConfirmationModal
          isOpen={isCancelModalOpen}
          onClose={() => setIsCancelModalOpen(false)}
          onConfirm={() => {
            props.onCancelAll?.();
            props.closeToast?.();
          }}
        />
      )}
    </ToasterItem>
  );
};
