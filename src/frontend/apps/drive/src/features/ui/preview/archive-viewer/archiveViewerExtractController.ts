import { useMemo, useState } from "react";
import { toast } from "react-toastify";
import { useArchiveExtractionStatus, useStartArchiveExtraction } from "@/features/explorer/api/useArchiveExtraction";
import { useItem } from "@/features/explorer/hooks/useQueries";
import { useArchiveJobLifecycleController } from "@/features/explorer/components/toasts/archiveJobLifecycleController";

export const getArchiveViewerDefaultDestinationFolderId = (
  archiveDetailsPath?: string,
) => {
  if (!archiveDetailsPath) return undefined;
  const parts = String(archiveDetailsPath).split(".");
  if (parts.length < 2) return undefined;
  return parts[parts.length - 2];
};

export const buildArchiveViewerExtractPayload = ({
  archiveItemId,
  destinationFolderId,
  extractMode,
  selectedPath,
}: {
  archiveItemId: string;
  destinationFolderId: string;
  extractMode: "all" | "selection";
  selectedPath?: string | null;
}) => {
  if (extractMode === "all") {
    return {
      destination_folder_id: destinationFolderId,
      item_id: archiveItemId,
      mode: "all" as const,
    };
  }

  return {
    destination_folder_id: destinationFolderId,
    item_id: archiveItemId,
    mode: "selection" as const,
    selection_paths: selectedPath ? [selectedPath] : [],
  };
};

export const useArchiveViewerExtractController = ({
  allowExtraction,
  archiveDetailsItemId,
  archiveItemId,
  selectedPath,
  t,
}: {
  allowExtraction: boolean;
  archiveDetailsItemId?: string;
  archiveItemId: string;
  selectedPath?: string | null;
  t: (key: string) => string;
}) => {
  const [isExtractModalOpen, setIsExtractModalOpen] = useState(false);
  const [extractMode, setExtractMode] = useState<"all" | "selection">("all");
  const [jobId, setJobId] = useState<string | null>(null);
  const [lastDestinationFolderId, setLastDestinationFolderId] = useState<
    string | null
  >(null);

  const startExtraction = useStartArchiveExtraction();
  const extractionStatus = useArchiveExtractionStatus(jobId ?? undefined);
  useArchiveJobLifecycleController({
    destinationFolderId: lastDestinationFolderId,
    jobId,
    onDone: () => {
      toast.success(t("archive_viewer.extract.done"));
    },
    onFailed: (detail) => {
      toast.error(detail || t("archive_viewer.extract.failed"));
    },
    status: extractionStatus.data,
  });

  const { data: archiveDetails } = useItem(archiveDetailsItemId ?? "", {
    enabled: Boolean(allowExtraction && archiveDetailsItemId),
  });

  const defaultDestinationFolderId = useMemo(
    () => getArchiveViewerDefaultDestinationFolderId(archiveDetails?.path),
    [archiveDetails?.path],
  );

  const onOpenExtractModal = (mode: "all" | "selection") => {
    setExtractMode(mode);
    setIsExtractModalOpen(true);
  };

  const onCloseExtractModal = () => {
    setIsExtractModalOpen(false);
  };

  const onConfirmExtract = async (destinationFolderId: string | undefined) => {
    if (!allowExtraction) return;
    if (!destinationFolderId) return;
    setIsExtractModalOpen(false);
    try {
      setLastDestinationFolderId(destinationFolderId);
      const payload = buildArchiveViewerExtractPayload({
        archiveItemId,
        destinationFolderId,
        extractMode,
        selectedPath,
      });
      const response = await startExtraction.mutateAsync(payload);
      setJobId(response.job_id);
      toast.success(t("archive_viewer.extract.started"));
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : t("archive_viewer.errors.unknown"),
      );
    }
  };

  return {
    defaultDestinationFolderId,
    extractionStatus,
    isExtractModalOpen,
    jobId,
    onCloseExtractModal,
    onConfirmExtract,
    onOpenExtractModal,
  };
};
