import { useEffect, useMemo, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

type ArchiveJobLifecycleStatus = {
  state?: "queued" | "running" | "done" | "failed" | "unknown";
  errors?: Array<{ detail?: string }>;
};

type ArchiveJobLifecycleStateParams = {
  destinationFolderId?: string | null;
  jobId?: string | null;
  lastHandledJobId?: string | null;
  status?: ArchiveJobLifecycleStatus;
};

export const getArchiveJobLifecycleState = ({
  destinationFolderId,
  jobId,
  lastHandledJobId,
  status,
}: ArchiveJobLifecycleStateParams) => {
  const terminalState =
    status?.state === "done" || status?.state === "failed"
      ? status.state
      : undefined;

  return {
    errorDetail: status?.errors?.[0]?.detail,
    isRunning:
      status?.state === "queued" ||
      status?.state === "running" ||
      status?.state === "unknown",
    shouldHandleTerminal:
      Boolean(jobId) &&
      Boolean(terminalState) &&
      lastHandledJobId !== jobId,
    shouldInvalidateDestination:
      terminalState === "done" && Boolean(destinationFolderId),
    state: status?.state,
    terminalState,
  };
};

type UseArchiveJobLifecycleControllerParams = {
  destinationFolderId?: string | null;
  jobId?: string | null;
  onDone?: () => void;
  onFailed?: (detail?: string) => void;
  status?: ArchiveJobLifecycleStatus;
};

export const useArchiveJobLifecycleController = ({
  destinationFolderId,
  jobId,
  onDone,
  onFailed,
  status,
}: UseArchiveJobLifecycleControllerParams) => {
  const queryClient = useQueryClient();
  const lastHandledJobIdRef = useRef<string | null>(null);

  const lifecycle = useMemo(
    () =>
      getArchiveJobLifecycleState({
        destinationFolderId,
        jobId,
        lastHandledJobId: lastHandledJobIdRef.current,
        status,
      }),
    [destinationFolderId, jobId, status],
  );

  useEffect(() => {
    if (!lifecycle.shouldHandleTerminal || !jobId) {
      return;
    }

    lastHandledJobIdRef.current = jobId;

    if (lifecycle.shouldInvalidateDestination && destinationFolderId) {
      queryClient.invalidateQueries({
        queryKey: ["items", destinationFolderId, "children", "infinite"],
      });
    }

    if (lifecycle.terminalState === "done") {
      onDone?.();
      return;
    }

    onFailed?.(lifecycle.errorDetail);
  }, [
    destinationFolderId,
    jobId,
    lifecycle.errorDetail,
    lifecycle.shouldHandleTerminal,
    lifecycle.shouldInvalidateDestination,
    lifecycle.terminalState,
    onDone,
    onFailed,
    queryClient,
  ]);

  return lifecycle;
};
