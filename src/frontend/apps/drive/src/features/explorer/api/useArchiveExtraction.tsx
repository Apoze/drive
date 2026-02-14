import { fetchAPI } from "@/features/api/fetchApi";
import { useMutation, useQuery } from "@tanstack/react-query";

export type ArchiveExtractionMode = "all" | "selection";

export type StartArchiveExtractionPayload = {
  item_id: string;
  destination_folder_id: string;
  mode: ArchiveExtractionMode;
  selection_paths?: string[];
};

export type ArchiveExtractionStatus = {
  state: "queued" | "running" | "done" | "failed" | "unknown";
  progress: {
    files_done: number;
    total: number;
    bytes_done: number;
    bytes_total: number;
  };
  errors?: Array<{ detail?: string }>;
};

export const useStartArchiveExtraction = () => {
  return useMutation({
    mutationFn: async (payload: StartArchiveExtractionPayload) => {
      const response = await fetchAPI("archive-extractions/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      return (await response.json()) as { job_id: string };
    },
  });
};

export const useArchiveExtractionStatus = (jobId?: string) => {
  return useQuery({
    queryKey: ["archive-extractions", jobId],
    enabled: !!jobId,
    queryFn: async () => {
      const response = await fetchAPI(`archive-extractions/${jobId}/`);
      return (await response.json()) as ArchiveExtractionStatus;
    },
    refetchInterval: (query) => {
      const data = query.state.data as ArchiveExtractionStatus | undefined;
      if (!data) return 1000;
      if (data.state === "done" || data.state === "failed") return false;
      return 1000;
    },
  });
};

