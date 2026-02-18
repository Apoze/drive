import React, { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { Icon } from "@gouvfr-lasuite/ui-kit";
import { useVirtualizer } from "@tanstack/react-virtual";
import { toast } from "react-toastify";
import { useQueryClient } from "@tanstack/react-query";
import prettyBytes from "pretty-bytes";
import { ArchiveExtractionModal } from "./ArchiveExtractionModal";
import {
  useArchiveExtractionStatus,
  useStartArchiveExtraction,
} from "@/features/explorer/api/useArchiveExtraction";
import { useItem } from "@/features/explorer/hooks/useQueries";
import { getIconByMimeType } from "@/features/explorer/components/icons/ItemIcon";

type ArchiveItem = {
  id: string;
  title: string;
  size: number;
  mimetype: string;
  url?: string;
};

type ArchiveEntry = {
  path: string;
  isDirectory: boolean;
  uncompressedSize: number;
  compressedSize?: number;
  lastModified?: number | null;
};

type ZipWorkerRequest =
  | { requestId: number; type: "list"; url: string }
  | { requestId: number; type: "readText"; url: string; path: string }
  | { requestId: number; type: "readBinary"; url: string; path: string };

type ZipWorkerRequestWithoutId =
  | { type: "list"; url: string }
  | { type: "readText"; url: string; path: string }
  | { type: "readBinary"; url: string; path: string };

type ZipWorkerResponse =
  | { requestId: number; type: "list:ok"; entries: ArchiveEntry[] }
  | { requestId: number; type: "readText:ok"; text: string }
  | { requestId: number; type: "readBinary:ok"; buffer: ArrayBuffer }
  | { requestId: number; type: "error"; message: string; code?: string };

type LibarchiveFile = {
  name?: string;
  size?: number;
  lastModified?: number;
  extract?: () => Promise<Blob>;
};

type LibarchiveArchive = {
  hasEncryptedData: () => Promise<boolean>;
  getFilesArray: () => Promise<Array<{ file: LibarchiveFile; path: string }>>;
};

const MAX_TEXT_PREVIEW_BYTES = 200 * 1024;
const MAX_IMAGE_PREVIEW_BYTES = 10 * 1024 * 1024;

const isZipLike = (item: ArchiveItem) => {
  const name = item.title.toLowerCase();
  if (name.endsWith(".zip")) return true;
  if (item.mimetype === "application/zip") return true;
  return false;
};

const isImagePath = (path: string) => {
  const lower = path.toLowerCase();
  return (
    lower.endsWith(".png") ||
    lower.endsWith(".jpg") ||
    lower.endsWith(".jpeg") ||
    lower.endsWith(".gif") ||
    lower.endsWith(".webp") ||
    lower.endsWith(".bmp") ||
    lower.endsWith(".svg")
  );
};

const isTextPath = (path: string) => {
  const lower = path.toLowerCase();
  return (
    lower.endsWith(".txt") ||
    lower.endsWith(".md") ||
    lower.endsWith(".csv") ||
    lower.endsWith(".log") ||
    lower.endsWith(".json") ||
    lower.endsWith(".xml") ||
    lower.endsWith(".yaml") ||
    lower.endsWith(".yml") ||
    lower.endsWith(".js") ||
    lower.endsWith(".ts") ||
    lower.endsWith(".css") ||
    lower.endsWith(".scss") ||
    lower.endsWith(".py") ||
    lower.endsWith(".java") ||
    lower.endsWith(".go") ||
    lower.endsWith(".rs")
  );
};

const downloadBlob = (filename: string, blob: Blob) => {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
};

const getEntryDisplayParts = (path: string) => {
  const normalized = path.replace(/\/+$/, "");
  const parts = normalized.split("/");
  const name = parts.pop() || normalized;
  const dir = parts.join("/");
  return { name, dir };
};

type SortKey = "name" | "size";
type SortDir = "asc" | "desc";

export const ArchiveViewer = ({
  archiveItem,
  onDownloadArchive,
}: {
  archiveItem: ArchiveItem;
  onDownloadArchive?: () => void;
}) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [backend, setBackend] = useState<"zip" | "libarchive" | "none">("none");
  const [query, setQuery] = useState("");
  const [entries, setEntries] = useState<ArchiveEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const [previewKind, setPreviewKind] = useState<"empty" | "text" | "image">(
    "empty"
  );
  const [previewText, setPreviewText] = useState<string>("");
  const [previewImageUrl, setPreviewImageUrl] = useState<string>("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const previewRequestIdRef = useRef(0);
  const [isExtractModalOpen, setIsExtractModalOpen] = useState(false);
  const [extractMode, setExtractMode] = useState<"all" | "selection">("all");
  const [jobId, setJobId] = useState<string | null>(null);
  const [lastDestinationFolderId, setLastDestinationFolderId] = useState<
    string | null
  >(null);
  const lastNotifiedJobIdRef = useRef<string | null>(null);

  const workerRef = useRef<Worker | null>(null);
  const nextRequestIdRef = useRef(1);
  const pendingRef = useRef(
    new Map<
      number,
      {
        resolve: (value: ZipWorkerResponse) => void;
        reject: (error: Error) => void;
      }
    >()
  );
  const libarchiveRef = useRef<{
    archive: LibarchiveArchive;
    fileByPath: Map<string, LibarchiveFile>;
  } | null>(null);
  const libarchiveInitRef = useRef(false);

  const startExtraction = useStartArchiveExtraction();
  const extractionStatus = useArchiveExtractionStatus(jobId ?? undefined);
  const { data: archiveDetails } = useItem(archiveItem.id, {
    enabled: Boolean(archiveItem.id),
  });

  const defaultDestinationFolderId = useMemo(() => {
    const path = archiveDetails?.path;
    if (!path) return undefined;
    const parts = String(path).split(".");
    if (parts.length < 2) return undefined;
    return parts[parts.length - 2];
  }, [archiveDetails?.path]);

  const selectedEntry = useMemo(() => {
    if (!selectedPath) return null;
    return entries.find((e) => e.path === selectedPath) ?? null;
  }, [entries, selectedPath]);

  const sortedEntries = useMemo(() => {
    const dirFactor = sortDir === "asc" ? 1 : -1;
    const out = [...entries];
    out.sort((a, b) => {
      if (sortKey === "size") {
        const diff = (a.uncompressedSize ?? 0) - (b.uncompressedSize ?? 0);
        if (diff !== 0) return diff * dirFactor;
        return a.path.localeCompare(b.path) * dirFactor;
      }

      const aDisplay = getEntryDisplayParts(a.path);
      const bDisplay = getEntryDisplayParts(b.path);
      const byName = aDisplay.name.localeCompare(bDisplay.name);
      if (byName !== 0) return byName * dirFactor;
      const byDir = aDisplay.dir.localeCompare(bDisplay.dir);
      if (byDir !== 0) return byDir * dirFactor;
      return a.path.localeCompare(b.path) * dirFactor;
    });
    return out;
  }, [entries, sortDir, sortKey]);

  const filteredEntries = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return sortedEntries;
    return sortedEntries.filter((e) => e.path.toLowerCase().includes(q));
  }, [query, sortedEntries]);

  const parentRef = useRef<HTMLDivElement | null>(null);
  const rowVirtualizer = useVirtualizer({
    count: filteredEntries.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 52,
    overscan: 15,
  });

  const ensureWorker = () => {
    if (workerRef.current) return workerRef.current;
    const worker = new Worker(new URL("./workers/zip.worker.ts", import.meta.url), {
      type: "module",
    });
    worker.onmessage = (event: MessageEvent<ZipWorkerResponse>) => {
      const pending = pendingRef.current.get(event.data.requestId);
      if (!pending) return;
      pendingRef.current.delete(event.data.requestId);
      pending.resolve(event.data);
    };
    workerRef.current = worker;
    return worker;
  };

  const callWorker = async (payload: ZipWorkerRequestWithoutId) => {
    const worker = ensureWorker();
    const requestId = nextRequestIdRef.current++;
    const response = await new Promise<ZipWorkerResponse>((resolve, reject) => {
      pendingRef.current.set(requestId, { resolve, reject });
      worker.postMessage({ ...payload, requestId } as ZipWorkerRequest);
    });
    if (response.type === "error") {
      throw new Error(response.message);
    }
    return response;
  };

  const clearPreview = () => {
    previewRequestIdRef.current += 1;
    setPreviewKind("empty");
    setPreviewText("");
    setPreviewError(null);
    setPreviewLoading(false);
    if (previewImageUrl) {
      URL.revokeObjectURL(previewImageUrl);
      setPreviewImageUrl("");
    }
  };

  const ensureLibarchiveInit = async () => {
    if (libarchiveInitRef.current) return;
    const { Archive } = await import("libarchive.js");
    Archive.init({
      workerUrl: "/vendor/libarchive/worker-bundle.js",
    });
    libarchiveInitRef.current = true;
  };

  useEffect(() => {
    return () => {
      if (workerRef.current) {
        workerRef.current.terminate();
        workerRef.current = null;
      }
      pendingRef.current.clear();
      libarchiveRef.current = null;
      if (previewImageUrl) {
        URL.revokeObjectURL(previewImageUrl);
      }
    };
  }, []);

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
      setSelectedPath(null);
      libarchiveRef.current = null;
      try {
        if (isZipLike(archiveItem)) {
          setBackend("zip");
          const res = await callWorker({ type: "list", url });
          if (res.type !== "list:ok") return;
          if (cancelled) return;
          setEntries(res.entries.filter((e) => !e.isDirectory));
        } else {
          setBackend("libarchive");
          const maxBlobBytes = 50 * 1024 * 1024; // 50 MiB
          if (Number(archiveItem.size ?? 0) > maxBlobBytes) {
            throw new Error(
              t("archive_viewer.errors.preview_too_large", {
                max: prettyBytes(maxBlobBytes),
              })
            );
          }
          await ensureLibarchiveInit();
          const resp = await fetch(url, { credentials: "include" });
          if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
          }
          const blob = await resp.blob();
          const { Archive } = await import("libarchive.js");
          const file = new File([blob], archiveItem.title || "archive", {
            type: archiveItem.mimetype || "application/octet-stream",
          });
          const archive = (await Archive.open(file)) as unknown as LibarchiveArchive;
          const encrypted = await archive.hasEncryptedData();
          if (encrypted) {
            throw new Error(t("archive_viewer.errors.encrypted_archive"));
          }
          const filesArray = await archive.getFilesArray();
          const fileByPath = new Map<string, LibarchiveFile>();
          const libEntries: ArchiveEntry[] = filesArray
            .map(({ file, path }) => {
              const dir = path ?? "";
              const name = file?.name ?? "";
              const full = `${dir}${name}`;
              fileByPath.set(full, file);
              return {
                path: full,
                isDirectory: Boolean(full.endsWith("/")),
                uncompressedSize: Number(file?.size ?? 0),
                lastModified: file?.lastModified
                  ? new Date(file.lastModified).getTime()
                  : null,
              };
            })
            .filter((e) => e.path);
          libarchiveRef.current = { archive, fileByPath };
          if (cancelled) return;
          setEntries(libEntries.filter((e) => !e.isDirectory));
        }
      } catch (e) {
        if (cancelled) return;
        setBackend("none");
        setError(
          e instanceof Error ? e.message : t("archive_viewer.errors.unknown")
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [archiveItem.id, archiveItem.mimetype, archiveItem.title, archiveItem.url, t]);

  const previewEntry = async (entry: ArchiveEntry) => {
    const url = archiveItem.url;
    if (!url) return;
    const requestId = (previewRequestIdRef.current += 1);

    const path = entry.path;
    setPreviewLoading(true);
    setPreviewError(null);

    try {
      if (isTextPath(path)) {
        if (entry.uncompressedSize > MAX_TEXT_PREVIEW_BYTES) {
          setPreviewKind("empty");
          setPreviewError(t("archive_viewer.errors.too_large_to_preview_text"));
          return;
        }
        if (backend === "zip") {
          const res = await callWorker({ type: "readText", url, path });
          if (previewRequestIdRef.current !== requestId) return;
          if (res.type !== "readText:ok") return;
          setPreviewKind("text");
          setPreviewText(res.text);
        } else if (backend === "libarchive") {
          const file = libarchiveRef.current?.fileByPath.get(path);
          if (!file?.extract) {
            throw new Error(t("archive_viewer.errors.unsupported_preview_type"));
          }
          const extracted: File = await file.extract();
          if (previewRequestIdRef.current !== requestId) return;
          const text = await extracted.text();
          if (previewRequestIdRef.current !== requestId) return;
          setPreviewKind("text");
          setPreviewText(text);
        } else {
          throw new Error(t("archive_viewer.errors.unsupported_preview_type"));
        }
        return;
      }

      if (isImagePath(path)) {
        if (entry.uncompressedSize > MAX_IMAGE_PREVIEW_BYTES) {
          setPreviewKind("empty");
          setPreviewError(t("archive_viewer.errors.too_large_to_preview_image"));
          return;
        }
        let blob: Blob;
        if (backend === "zip") {
          const res = await callWorker({ type: "readBinary", url, path });
          if (previewRequestIdRef.current !== requestId) return;
          if (res.type !== "readBinary:ok") return;
          blob = new Blob([res.buffer]);
        } else if (backend === "libarchive") {
          const file = libarchiveRef.current?.fileByPath.get(path);
          if (!file?.extract) {
            throw new Error(t("archive_viewer.errors.unsupported_preview_type"));
          }
          blob = await file.extract();
          if (previewRequestIdRef.current !== requestId) return;
        } else {
          throw new Error(t("archive_viewer.errors.unsupported_preview_type"));
        }
        const objectUrl = URL.createObjectURL(blob);
        if (previewRequestIdRef.current !== requestId) {
          URL.revokeObjectURL(objectUrl);
          return;
        }
        setPreviewKind("image");
        setPreviewImageUrl(objectUrl);
        return;
      }

      setPreviewKind("empty");
      setPreviewError(null);
    } catch (e) {
      if (previewRequestIdRef.current !== requestId) return;
      setPreviewKind("empty");
      setPreviewError(
        e instanceof Error ? e.message : t("archive_viewer.errors.unknown")
      );
    } finally {
      if (previewRequestIdRef.current !== requestId) return;
      setPreviewLoading(false);
    }
  };

  useEffect(() => {
    clearPreview();
    if (!selectedEntry) return;
    void previewEntry(selectedEntry);
  }, [selectedEntry?.path]);

  const onDownloadSelected = async () => {
    const url = archiveItem.url;
    if (!url || !selectedEntry) return;
    try {
      let blob: Blob;
      if (backend === "zip") {
        const res = await callWorker({
          type: "readBinary",
          url,
          path: selectedEntry.path,
        });
        if (res.type !== "readBinary:ok") return;
        blob = new Blob([res.buffer]);
      } else if (backend === "libarchive") {
        const file = libarchiveRef.current?.fileByPath.get(selectedEntry.path);
        if (!file?.extract) {
          throw new Error();
        }
        blob = await file.extract();
      } else {
        throw new Error();
      }
      downloadBlob(
        selectedEntry.path.split("/").pop() || "download",
        blob
      );
    } catch {
      // handled by UI via preview errors; keep silent here
    }
  };

  const onOpenExtractModal = (mode: "all" | "selection") => {
    setExtractMode(mode);
    setIsExtractModalOpen(true);
  };

  const toggleSort = (key: SortKey) => {
    if (sortKey !== key) {
      setSortKey(key);
      setSortDir("asc");
      return;
    }
    setSortDir((d) => (d === "asc" ? "desc" : "asc"));
  };

  const onConfirmExtract = async (destinationFolderId: string | undefined) => {
    if (!destinationFolderId) return;
    setIsExtractModalOpen(false);
    try {
      setLastDestinationFolderId(destinationFolderId);
      const payload =
        extractMode === "all"
          ? {
              item_id: archiveItem.id,
              destination_folder_id: destinationFolderId,
              mode: "all" as const,
            }
          : {
              item_id: archiveItem.id,
              destination_folder_id: destinationFolderId,
              mode: "selection" as const,
              selection_paths: selectedEntry ? [selectedEntry.path] : [],
            };
      const res = await startExtraction.mutateAsync(payload);
      setJobId(res.job_id);
      toast.success(t("archive_viewer.extract.started"));
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : t("archive_viewer.errors.unknown")
      );
    }
  };

  useEffect(() => {
    if (!jobId || !extractionStatus.data) return;

    const { state } = extractionStatus.data;
    if (state !== "done" && state !== "failed") return;
    if (lastNotifiedJobIdRef.current === jobId) return;
    lastNotifiedJobIdRef.current = jobId;

    if (state === "done") {
      if (lastDestinationFolderId) {
        queryClient.invalidateQueries({
          queryKey: ["items", lastDestinationFolderId, "children", "infinite"],
        });
      }
      toast.success(t("archive_viewer.extract.done"));
      return;
    }

    const detail = extractionStatus.data.errors?.[0]?.detail;
    toast.error(detail || t("archive_viewer.extract.failed"));
  }, [
    extractionStatus.data,
    jobId,
    lastDestinationFolderId,
    queryClient,
    t,
  ]);

  return (
    <div className="archive-viewer">
      <div className="archive-viewer__toolbar">
        <div className="archive-viewer__toolbar-left">
          <div className="archive-viewer__toolbar-title">
            <span className="archive-viewer__toolbar-title-text">
              {t("archive_viewer.contents_title")}
            </span>
            <span className="archive-viewer__toolbar-title-meta">
              {t("archive_viewer.contents_count", { count: entries.length })}
              {backend !== "none" && (
                <>
                  {" "}
                  ·{" "}
                  {backend === "zip"
                    ? t("archive_viewer.backend.zip_range")
                    : t("archive_viewer.backend.downloaded")}
                </>
              )}
            </span>
          </div>
        </div>
        <div className="archive-viewer__toolbar-right">
          <Button
            size="small"
            variant="tertiary"
            onClick={() => onOpenExtractModal("all")}
            icon={<Icon name="unarchive" />}
          >
            {t("archive_viewer.actions.extract_all")}
          </Button>
          <Button
            size="small"
            variant="tertiary"
            onClick={() => onOpenExtractModal("selection")}
            disabled={!selectedEntry}
            icon={<Icon name="unarchive" />}
          >
            {t("archive_viewer.actions.extract_selected")}
          </Button>
          {onDownloadArchive && (
            <Button
              size="small"
              variant="tertiary"
              onClick={onDownloadArchive}
              icon={<Icon name="file_download" />}
            >
              {t("archive_viewer.actions.download_archive")}
            </Button>
          )}
        </div>
      </div>

      {jobId && (extractionStatus.data || extractionStatus.isFetching) && (
        <div className="archive-viewer__job">
          <span className="archive-viewer__job-state">
            {extractionStatus.data
              ? t("archive_viewer.extract.status", {
                  state: extractionStatus.data.state,
                  done: extractionStatus.data.progress.files_done,
                  total: extractionStatus.data.progress.total,
                })
              : t("archive_viewer.extract.status_loading")}
          </span>
        </div>
      )}

      <div className="archive-viewer__content">
        <div className="archive-viewer__panel archive-viewer__left">
          <div className="archive-viewer__search">
            <Icon name="search" />
            <input
              aria-label={t("archive_viewer.search_aria")}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("archive_viewer.search_placeholder")}
              type="text"
            />
            {query && (
              <button
                type="button"
                className="archive-viewer__search-clear"
                onClick={() => setQuery("")}
                aria-label={t("archive_viewer.search_clear_aria")}
              >
                <Icon name="close" />
              </button>
            )}
          </div>
          <div className="archive-viewer__list-header" role="row">
            <button
              type="button"
              className={`archive-viewer__list-header-btn ${
                sortKey === "name" ? "is-active" : ""
              }`}
              onClick={() => toggleSort("name")}
            >
              {t("explorer.grid.name")}
              {sortKey === "name" && (
                <span className="archive-viewer__sort-indicator">
                  {sortDir === "asc" ? "↑" : "↓"}
                </span>
              )}
            </button>
            <button
              type="button"
              className={`archive-viewer__list-header-btn archive-viewer__list-header-btn--size ${
                sortKey === "size" ? "is-active" : ""
              }`}
              onClick={() => toggleSort("size")}
            >
              {t("explorer.metadata.size")}
              {sortKey === "size" && (
                <span className="archive-viewer__sort-indicator">
                  {sortDir === "asc" ? "↑" : "↓"}
                </span>
              )}
            </button>
          </div>
          {loading && (
            <div className="archive-viewer__state">
              <Icon name="progress_activity" /> {t("archive_viewer.states.loading")}
            </div>
          )}
          {error && !loading && (
            <div className="archive-viewer__state archive-viewer__state--error">
              {error}
            </div>
          )}
          {!error && !loading && filteredEntries.length === 0 && (
            <div className="archive-viewer__state">
              {t("archive_viewer.states.empty")}
            </div>
          )}
          {!error && !loading && filteredEntries.length > 0 && (
            <div ref={parentRef} className="archive-viewer__list" role="listbox">
              <div
                style={{
                  height: `${rowVirtualizer.getTotalSize()}px`,
                  width: "100%",
                  position: "relative",
                }}
              >
                {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                  const entry = filteredEntries[virtualRow.index];
                  const isSelected = entry.path === selectedPath;
                  const display = getEntryDisplayParts(entry.path);
                  const icon = getIconByMimeType(
                    "application/octet-stream",
                    "mini",
                    display.name
                  );
                  return (
                    <div
                      key={entry.path}
                      className={`archive-viewer__row ${
                        isSelected ? "archive-viewer__row--selected" : ""
                      }`}
                      style={{
                        position: "absolute",
                        top: 0,
                        left: 0,
                        width: "100%",
                        height: `${virtualRow.size}px`,
                        transform: `translateY(${virtualRow.start}px)`,
                      }}
                      onClick={() => setSelectedPath(entry.path)}
                      role="option"
                      tabIndex={0}
                      aria-selected={isSelected}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSelectedPath(entry.path);
                        }
                      }}
                    >
                      <div className="archive-viewer__row-main">
                        <img
                          className="archive-viewer__row-icon"
                          src={icon.src}
                          alt=""
                          draggable="false"
                        />
                        <div className="archive-viewer__row-text">
                          <div className="archive-viewer__row-name">
                            {display.name}
                          </div>
                          {display.dir && (
                            <div className="archive-viewer__row-dir">
                              {display.dir}
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="archive-viewer__row-meta">
                        <span className="archive-viewer__row-size">
                          {prettyBytes(entry.uncompressedSize || 0)}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        <div className="archive-viewer__panel archive-viewer__right">
          {!selectedEntry && (
            <div className="archive-viewer__state">
              {t("archive_viewer.states.select_a_file")}
            </div>
          )}

          {selectedEntry && (
            <div className="archive-viewer__preview">
              <div className="archive-viewer__preview-header">
                <div className="archive-viewer__preview-title">
                  {getEntryDisplayParts(selectedEntry.path).name}
                  <div className="archive-viewer__preview-subtitle">
                    {prettyBytes(selectedEntry.uncompressedSize || 0)} ·{" "}
                    {selectedEntry.path}
                  </div>
                </div>
                <div className="archive-viewer__preview-actions">
                  <Button
                    size="small"
                    variant="tertiary"
                    onClick={onDownloadSelected}
                    icon={<Icon name="file_download" />}
                  >
                    {t("archive_viewer.actions.download_file")}
                  </Button>
                </div>
              </div>

              {previewLoading && (
                <div className="archive-viewer__state">
                  <Icon name="progress_activity" />{" "}
                  {t("archive_viewer.states.loading_preview")}
                </div>
              )}
              {previewError && !previewLoading && (
                <div className="archive-viewer__state archive-viewer__state--error">
                  {previewError}
                </div>
              )}

              {!previewLoading && !previewError && previewKind === "text" && (
                <pre className="archive-viewer__text">{previewText}</pre>
              )}
              {!previewLoading && !previewError && previewKind === "image" && (
                <div className="archive-viewer__image-container">
                  <img
                    className="archive-viewer__image"
                    src={previewImageUrl}
                    alt={selectedEntry.path}
                  />
                </div>
              )}
              {!previewLoading && !previewError && previewKind === "empty" && (
                <div className="archive-viewer__state">
                  {t("archive_viewer.states.no_preview")}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <ArchiveExtractionModal
        isOpen={isExtractModalOpen}
        onClose={() => setIsExtractModalOpen(false)}
        initialFolderId={defaultDestinationFolderId}
        onConfirm={onConfirmExtract}
      />
    </div>
  );
};
