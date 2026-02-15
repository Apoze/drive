import { fetchAPI } from "@/features/api/fetchApi";
import { useMutation, useQuery } from "@tanstack/react-query";

export type StartArchiveZipPayload = {
  item_ids: string[];
  destination_folder_id: string;
  archive_name: string;
};

export type ArchiveZipStatus = {
  state: "queued" | "running" | "done" | "failed" | "unknown";
  progress: {
    files_done: number;
    total: number;
    bytes_done: number;
    bytes_total: number;
  };
  errors?: Array<{ detail?: string }>;
  result_item_id?: string;
};

export const useStartArchiveZip = () => {
  return useMutation({
    mutationFn: async (payload: StartArchiveZipPayload) => {
      const response = await fetchAPI("archive-zips/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      return (await response.json()) as { job_id: string };
    },
  });
};

export const useArchiveZipStatus = (jobId?: string) => {
  return useQuery({
    queryKey: ["archive-zips", jobId],
    enabled: !!jobId,
    queryFn: async () => {
      const response = await fetchAPI(`archive-zips/${jobId}/`);
      return (await response.json()) as ArchiveZipStatus;
    },
    refetchInterval: (query) => {
      const data = query.state.data as ArchiveZipStatus | undefined;
      if (!data) return 1000;
      if (data.state === "done" || data.state === "failed") return false;
      return 1000;
    },
  });
};

