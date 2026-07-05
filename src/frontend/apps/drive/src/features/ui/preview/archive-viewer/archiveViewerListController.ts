import { useMemo, useState } from "react";
import type { ArchiveEntry } from "./archiveViewerRuntime";

export type ArchiveViewerSortKey = "name" | "size";
export type ArchiveViewerSortDir = "asc" | "desc";

export const getArchiveEntryDisplayParts = (path: string) => {
  const normalized = path.replace(/\/+$/, "");
  const parts = normalized.split("/");
  const name = parts.pop() || normalized;
  const dir = parts.join("/");
  return { dir, name };
};

export const getNextArchiveSortState = ({
  key,
  sortDir,
  sortKey,
}: {
  key: ArchiveViewerSortKey;
  sortDir: ArchiveViewerSortDir;
  sortKey: ArchiveViewerSortKey;
}) => {
  if (sortKey !== key) {
    return {
      sortDir: "asc" as const,
      sortKey: key,
    };
  }

  return {
    sortDir: (sortDir === "asc" ? "desc" : "asc") as ArchiveViewerSortDir,
    sortKey,
  };
};

export const getSortedArchiveEntries = ({
  entries,
  sortDir,
  sortKey,
}: {
  entries: ArchiveEntry[];
  sortDir: ArchiveViewerSortDir;
  sortKey: ArchiveViewerSortKey;
}) => {
  const dirFactor = sortDir === "asc" ? 1 : -1;
  const out = [...entries];
  out.sort((a, b) => {
    if (sortKey === "size") {
      const diff = (a.uncompressedSize ?? 0) - (b.uncompressedSize ?? 0);
      if (diff !== 0) return diff * dirFactor;
      return a.path.localeCompare(b.path) * dirFactor;
    }

    const aDisplay = getArchiveEntryDisplayParts(a.path);
    const bDisplay = getArchiveEntryDisplayParts(b.path);
    const byName = aDisplay.name.localeCompare(bDisplay.name);
    if (byName !== 0) return byName * dirFactor;
    const byDir = aDisplay.dir.localeCompare(bDisplay.dir);
    if (byDir !== 0) return byDir * dirFactor;
    return a.path.localeCompare(b.path) * dirFactor;
  });
  return out;
};

export const getFilteredArchiveEntries = ({
  entries,
  query,
}: {
  entries: ArchiveEntry[];
  query: string;
}) => {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return entries;
  return entries.filter((entry) =>
    entry.path.toLowerCase().includes(normalizedQuery),
  );
};

export const useArchiveViewerListController = ({
  entries,
}: {
  entries: ArchiveEntry[];
}) => {
  const [query, setQuery] = useState("");
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<ArchiveViewerSortKey>("name");
  const [sortDir, setSortDir] = useState<ArchiveViewerSortDir>("asc");

  const selectedEntry = useMemo(() => {
    if (!selectedPath) return null;
    return entries.find((entry) => entry.path === selectedPath) ?? null;
  }, [entries, selectedPath]);

  const sortedEntries = useMemo(
    () =>
      getSortedArchiveEntries({
        entries,
        sortDir,
        sortKey,
      }),
    [entries, sortDir, sortKey],
  );

  const filteredEntries = useMemo(
    () =>
      getFilteredArchiveEntries({
        entries: sortedEntries,
        query,
      }),
    [query, sortedEntries],
  );

  const toggleSort = (key: ArchiveViewerSortKey) => {
    const next = getNextArchiveSortState({
      key,
      sortDir,
      sortKey,
    });
    setSortKey(next.sortKey);
    setSortDir(next.sortDir);
  };

  return {
    filteredEntries,
    query,
    selectedEntry,
    selectedPath,
    setQuery,
    setSelectedPath,
    sortDir,
    sortKey,
    toggleSort,
  };
};
