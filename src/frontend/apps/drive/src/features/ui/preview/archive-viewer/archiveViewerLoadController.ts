import { useEffect, useState } from "react";
import prettyBytes from "pretty-bytes";
import type { ArchiveBackend, ArchiveEntry, ArchiveItem, createArchiveViewerRuntime } from "./archiveViewerRuntime";

type ArchiveViewerRuntime = ReturnType<typeof createArchiveViewerRuntime>;

export const useArchiveViewerLoadController = ({
  archiveAccessMode,
  archiveItem,
  runtime,
  t,
}: {
  archiveAccessMode: "auto" | "download";
  archiveItem: ArchiveItem;
  runtime: ArchiveViewerRuntime;
  t: (key: string, values?: Record<string, unknown>) => string;
}) => {
  const [backend, setBackend] = useState<ArchiveBackend>("none");
  const [entries, setEntries] = useState<ArchiveEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const url = archiveItem.url;
    if (!url) {
      setError(t("archive_viewer.errors.no_url"));
      return;
    }

    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      setEntries([]);
      try {
        const result = await runtime.loadEntries({
          archiveAccessMode,
          archiveItem,
          encryptedArchiveMessage: t("archive_viewer.errors.encrypted_archive"),
          maxBlobBytes: 50 * 1024 * 1024,
          previewTooLargeMessage: t("archive_viewer.errors.preview_too_large", {
            max: prettyBytes(50 * 1024 * 1024),
          }),
        });
        if (cancelled) return;
        setBackend(result.backend);
        setEntries(result.entries);
      } catch (e) {
        if (cancelled) return;
        setBackend("none");
        setError(
          e instanceof Error ? e.message : t("archive_viewer.errors.unknown"),
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [
    archiveAccessMode,
    archiveItem.id,
    archiveItem.mimetype,
    archiveItem.size,
    archiveItem.title,
    archiveItem.url,
    runtime,
    t,
  ]);

  return {
    backend,
    entries,
    error,
    loading,
  };
};
