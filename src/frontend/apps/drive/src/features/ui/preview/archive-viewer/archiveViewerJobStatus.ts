import { ArchiveExtractionStatus } from "@/features/explorer/api/useArchiveExtraction";

type TranslateFn = (key: string, values?: Record<string, unknown>) => string;

export const getArchiveViewerJobStatusLabel = ({
  status,
  t,
}: {
  status?: ArchiveExtractionStatus;
  t: TranslateFn;
}) => {
  if (!status) {
    return t("archive_viewer.extract.status_loading");
  }

  return t("archive_viewer.extract.status", {
    done: status.progress.files_done,
    state: status.state,
    total: status.progress.total,
  });
};
