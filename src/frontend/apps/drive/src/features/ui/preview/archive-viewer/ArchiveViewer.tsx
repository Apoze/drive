import React, { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { Icon } from "@gouvfr-lasuite/ui-kit";
import { useVirtualizer } from "@tanstack/react-virtual";
import prettyBytes from "pretty-bytes";
import { ArchiveExtractionModal } from "./ArchiveExtractionModal";
import { useArchiveViewerExtractController } from "./archiveViewerExtractController";
import {
  getArchiveEntryDisplayParts,
  useArchiveViewerListController,
} from "./archiveViewerListController";
import { useArchiveViewerLoadController } from "./archiveViewerLoadController";
import { useArchiveViewerPreviewController } from "./archiveViewerPreviewController";
import { getArchiveViewerJobStatusLabel } from "./archiveViewerJobStatus";
import {
  type ArchiveItem,
  createArchiveViewerRuntime,
} from "./archiveViewerRuntime";
import { getIconByMimeType } from "@/features/explorer/components/icons/ItemIcon";

export const ArchiveViewer = ({
  archiveItem,
  onDownloadArchive,
  archiveDetailsItemId,
  allowExtraction = true,
  archiveAccessMode = "auto",
}: {
  archiveItem: ArchiveItem;
  onDownloadArchive?: () => void;
  archiveDetailsItemId?: string;
  allowExtraction?: boolean;
  archiveAccessMode?: "auto" | "download";
}) => {
  const { t } = useTranslation();
  const runtimeRef = useRef(createArchiveViewerRuntime());
  const { backend, entries, error, loading } = useArchiveViewerLoadController({
    archiveAccessMode,
    archiveItem,
    runtime: runtimeRef.current,
    t,
  });
  const {
    filteredEntries,
    query,
    selectedEntry,
    selectedPath,
    setQuery,
    setSelectedPath,
    sortDir,
    sortKey,
    toggleSort,
  } = useArchiveViewerListController({
    entries,
  });
  const {
    onDownloadSelected,
    previewError,
    previewImageUrl,
    previewKind,
    previewLoading,
    previewText,
  } = useArchiveViewerPreviewController({
    backend,
    runtime: runtimeRef.current,
    selectedEntry,
    t,
    url: archiveItem.url,
  });
  const {
    defaultDestinationFolderId,
    extractionStatus,
    isExtractModalOpen,
    jobId,
    onCloseExtractModal,
    onConfirmExtract,
    onOpenExtractModal,
  } = useArchiveViewerExtractController({
    allowExtraction,
    archiveDetailsItemId,
    archiveItemId: archiveItem.id,
    selectedPath,
    t,
  });

  const parentRef = useRef<HTMLDivElement | null>(null);
  const rowVirtualizer = useVirtualizer({
    count: filteredEntries.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 52,
    overscan: 15,
  });

  useEffect(() => () => {
    runtimeRef.current.dispose();
  }, []);

  useEffect(() => {
    setSelectedPath(null);
  }, [
    archiveAccessMode,
    archiveItem.id,
    archiveItem.mimetype,
    archiveItem.title,
    archiveItem.url,
    setSelectedPath,
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
          {allowExtraction && (
            <>
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
            </>
          )}
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

      {allowExtraction && jobId && (extractionStatus.data || extractionStatus.isFetching) && (
        <div className="archive-viewer__job">
          <span className="archive-viewer__job-state">
            {getArchiveViewerJobStatusLabel({
              status: extractionStatus.data,
              t,
            })}
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
                  const display = getArchiveEntryDisplayParts(entry.path);
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
                  {getArchiveEntryDisplayParts(selectedEntry.path).name}
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

      {allowExtraction && (
        <ArchiveExtractionModal
          isOpen={isExtractModalOpen}
          onClose={onCloseExtractModal}
          initialFolderId={defaultDestinationFolderId}
          onConfirm={onConfirmExtract}
        />
      )}
    </div>
  );
};
