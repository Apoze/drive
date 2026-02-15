import { useArchiveExtractionStatus } from "@/features/explorer/api/useArchiveExtraction";
import { useArchiveZipStatus } from "@/features/explorer/api/useArchiveZip";
import { ToasterItem, addToast } from "@/features/ui/components/toaster/Toaster";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import { ToastContentProps, toast } from "react-toastify";

export type ArchiveJobKind = "zip" | "unzip";

export type ArchiveJobToastProps = ToastContentProps & {
  kind: ArchiveJobKind;
  jobId: string;
  destinationFolderId: string;
};

export const ArchiveJobToast = ({
  kind,
  jobId,
  destinationFolderId,
  closeToast,
}: ArchiveJobToastProps) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const notifiedRef = useRef(false);

  const zipStatus = useArchiveZipStatus(kind === "zip" ? jobId : undefined);
  const unzipStatus = useArchiveExtractionStatus(
    kind === "unzip" ? jobId : undefined,
  );

  const status = kind === "zip" ? zipStatus.data : unzipStatus.data;
  const unknownTimerRef = useRef<number | null>(null);

  const pct = useMemo(() => {
    const p = status?.progress;
    if (!p) return undefined;
    if (p.bytes_total > 0) {
      return Math.floor((p.bytes_done / p.bytes_total) * 100);
    }
    if (p.total > 0) {
      return Math.floor((p.files_done / p.total) * 100);
    }
    return undefined;
  }, [status?.progress]);

  useEffect(() => {
    if (unknownTimerRef.current !== null) {
      window.clearTimeout(unknownTimerRef.current);
      unknownTimerRef.current = null;
    }

    if (status?.state === "unknown") {
      unknownTimerRef.current = window.setTimeout(() => {
        closeToast?.();
        addToast(
          <ToasterItem type="error">
            <span className="material-icons">
              {kind === "zip" ? "archive" : "unarchive"}
            </span>
            <span>{t("explorer.actions.archive.common.toast_unknown_job")}</span>
          </ToasterItem>,
        );
      }, 3000);
    }

    const state = status?.state;
    if (!state || state === "queued" || state === "running" || state === "unknown") {
      return;
    }
    if (notifiedRef.current) {
      return;
    }
    notifiedRef.current = true;

    queryClient.invalidateQueries({
      queryKey: ["items", destinationFolderId, "children", "infinite"],
    });

    closeToast?.();

    if (state === "done") {
      addToast(
        <ToasterItem>
          <span className="material-icons">
            {kind === "zip" ? "archive" : "unarchive"}
          </span>
          <span>
            {kind === "zip"
              ? t("explorer.actions.archive.zip.toast_done")
              : t("explorer.actions.archive.unzip.toast_done")}
          </span>
        </ToasterItem>,
      );
      return;
    }

    const detail = status?.errors?.[0]?.detail;
    addToast(
      <ToasterItem type="error">
        <span className="material-icons">
          {kind === "zip" ? "archive" : "unarchive"}
        </span>
        <span>
          {detail ||
            (kind === "zip"
              ? t("explorer.actions.archive.zip.toast_failed")
              : t("explorer.actions.archive.unzip.toast_failed"))}
        </span>
      </ToasterItem>,
    );
  }, [
    closeToast,
    destinationFolderId,
    kind,
    queryClient,
    status?.errors,
    status?.state,
    t,
  ]);

  return (
    <ToasterItem>
      <span className="material-icons">
        {kind === "zip" ? "archive" : "unarchive"}
      </span>
      <span>
        {kind === "zip"
          ? t("explorer.actions.archive.zip.toast_running")
          : t("explorer.actions.archive.unzip.toast_running")}
      </span>
      {pct !== undefined && (
        <span style={{ marginLeft: 8 }}>{pct}%</span>
      )}
    </ToasterItem>
  );
};

export const showArchiveJobToast = ({
  kind,
  jobId,
  destinationFolderId,
}: {
  kind: ArchiveJobKind;
  jobId: string;
  destinationFolderId: string;
}) => {
  toast(
    (props) => (
      <ArchiveJobToast
        {...props}
        kind={kind}
        jobId={jobId}
        destinationFolderId={destinationFolderId}
      />
    ),
    {
      position: "bottom-center",
      closeButton: false,
      className: "suite__toaster__wrapper",
      autoClose: false,
      hideProgressBar: true,
    },
  );
};
