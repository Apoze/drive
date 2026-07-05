import { MimeCategory } from "@/features/explorer/utils/mimeTypes";
import { Icon, IconType } from "@gouvfr-lasuite/ui-kit";
import {
  Button,
  Modal,
  ModalSize,
  Tooltip,
} from "@gouvfr-lasuite/cunningham-react";
import React, { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-toastify";
import { ImageViewer } from "../image-viewer/ImageViewer";
import { VideoPlayer } from "../video-player/VideoPlayer";
import { AudioPlayer } from "../audio-player/AudioPlayer";
import { PreviewPdf } from "../pdf-preview/PreviewPdf";
import { ArchiveViewer } from "../archive-viewer/ArchiveViewer";

import { NotSupportedPreview } from "../not-supported/NotSupportedPreview";
import { FileIcon } from "@/features/explorer/components/icons/ItemIcon";
import { useTranslation } from "react-i18next";
import { SuspiciousPreview } from "../suspicious/SuspiciousPreview";
import { WopiEditor } from "../wopi/WopiEditor";
import posthog from "posthog-js";
import { TextPreview } from "../text-preview/TextPreview";
import { APIError, errorToString } from "@/features/api/APIError";
import {
  getPreviewMimeCategory,
  isTextEligibleByRules,
  shouldUseWopiTextPreview,
} from "./previewRules";
import {
  defaultPreviewSource,
  type FilePreviewType,
  type PreviewSource,
  getTextPreviewQueryKey,
} from "./previewSource";
import { useResolvedPreviewFile } from "./useResolvedPreviewFile";
import { resolvePreviewViewerKind } from "./previewViewerState";

export type { FilePreviewType } from "./previewSource";

type FilePreviewData = FilePreviewType & {
  category: MimeCategory;
  isSuspicious?: boolean;
};

interface FilePreviewProps {
  isOpen: boolean;
  onClose?: () => void;
  title?: string;
  files?: FilePreviewType[];
  initialIndexFile?: number;
  openedFileId?: string;
  headerRightContent?: React.ReactNode;
  sidebarContent?: React.ReactNode;
  onChangeFile?: (file?: FilePreviewType) => void;
  handleDownloadFile?: (file?: FilePreviewType) => void;
  hideCloseButton?: boolean;
  hideNav?: boolean;
  onFileRename?: (file: FilePreviewType, newName: string) => void;
  source?: PreviewSource;
}

export const FilePreview = ({
  isOpen,
  onClose,
  title = "File Preview",
  files = [],
  initialIndexFile = -1,
  openedFileId,
  sidebarContent,
  headerRightContent,
  onChangeFile,
  handleDownloadFile,
  hideCloseButton,
  hideNav,
  onFileRename,
  source = defaultPreviewSource,
}: FilePreviewProps) => {
  const { t } = useTranslation();
  const [currentIndex, setCurrentIndex] = useState(initialIndexFile);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const queryClient = useQueryClient();
  const [isEditingText, setIsEditingText] = useState(false);
  const [textDraft, setTextDraft] = useState("");
  const [textBase, setTextBase] = useState("");
  const [textEtag, setTextEtag] = useState("");
  const [isTextTruncated, setIsTextTruncated] = useState(false);

  const data: FilePreviewData[] = useMemo(() => {
    return files?.map((file) => {
      const previewFilename = file.filename || file.title || "";
      return {
        ...file,
        is_wopi_supported: file.is_wopi_supported ?? false,
        category: getPreviewMimeCategory(file.mimetype, previewFilename),
      };
    });
  }, [files]);

  const currentFile: FilePreviewData | undefined =
    currentIndex > -1 ? data[currentIndex] : undefined;
  const { effectiveCurrentFile, isResolvingCurrentFile, resolvedPreviewQuery } =
    useResolvedPreviewFile(currentFile, source);
  const currentPreviewKind = effectiveCurrentFile?.preview_kind;

  const currentFilename =
    effectiveCurrentFile?.filename || effectiveCurrentFile?.title || "";
  const forceTextViewer = currentPreviewKind === "text";
  const shouldUseResolvedPreviewKind = Boolean(source.resolveFilePreview && currentFile);
  const shouldPreferWopiText = shouldUseWopiTextPreview(currentFilename);
  const baseTextEligible = Boolean(
    effectiveCurrentFile &&
      (forceTextViewer ||
        (!shouldUseResolvedPreviewKind &&
          isTextEligibleByRules(effectiveCurrentFile.mimetype, currentFilename))),
  );
  const shouldFetchText = Boolean(
    effectiveCurrentFile &&
      baseTextEligible &&
      (forceTextViewer ||
        !effectiveCurrentFile.is_wopi_supported ||
        !shouldPreferWopiText),
  );
  const canUpdateText = Boolean(effectiveCurrentFile?.can_update);
  const effectiveTextQueryKey = effectiveCurrentFile
    ? getTextPreviewQueryKey(source, effectiveCurrentFile)
    : ["item", undefined, "text"];

  const textQuery = useQuery({
    queryKey: effectiveTextQueryKey,
    enabled: shouldFetchText,
    refetchOnWindowFocus: false,
    retry: false,
    queryFn: async () => {
      return source.fetchTextContent?.(effectiveCurrentFile!) ?? null;
    },
  });

  const textEncoding = textQuery.data?.encoding ?? "utf-8";
  const isTextReadOnly = Boolean(textQuery.data?.read_only);
  const canEditText = canUpdateText && !isTextTruncated && !isTextReadOnly;
  const shouldRenderWopi = Boolean(
    effectiveCurrentFile &&
      (currentPreviewKind === "wopi" ||
        (effectiveCurrentFile.is_wopi_supported &&
          (!baseTextEligible || shouldPreferWopiText) &&
          !forceTextViewer)),
  );

  const useTextViewer = Boolean(
    effectiveCurrentFile &&
      shouldFetchText &&
      textQuery.data !== null,
  );

  useEffect(() => {
    setIsEditingText(false);
    setTextDraft("");
    setTextBase("");
    setTextEtag("");
    setIsTextTruncated(false);
  }, [effectiveCurrentFile?.id]);

  useEffect(() => {
    if (!useTextViewer) {
      return;
    }
    if (!textQuery.data) {
      return;
    }
    setTextDraft(textQuery.data.content ?? "");
    setTextBase(textQuery.data.content ?? "");
    setTextEtag(textQuery.data.etag ?? "");
    setIsTextTruncated(Boolean(textQuery.data.truncated));
  }, [useTextViewer, textQuery.data]);

  const isTextDirty = useTextViewer && isEditingText && textDraft !== textBase;

  const saveTextMutation = useMutation({
    mutationFn: async () => {
      if (!effectiveCurrentFile) {
        throw new Error("Missing current file");
      }
      if (!textEtag) {
        throw new Error("Missing ETag");
      }
      if (!source.saveTextContent) {
        throw new Error("Missing text save strategy");
      }
      return source.saveTextContent({
        file: effectiveCurrentFile,
        content: textDraft,
        etag: textEtag,
      });
    },
    onSuccess: (res) => {
      const newEtag = res?.etag ?? textEtag;
      setTextEtag(newEtag ?? "");
      setTextBase(textDraft);
      setIsEditingText(false);
      queryClient.setQueryData(effectiveTextQueryKey, (prev: unknown) => {
        if (!prev || !useTextViewer) {
          return prev;
        }
        const previousTextContent = prev as {
          content?: string;
          truncated?: boolean;
          etag?: string;
        };
        return {
          ...previousTextContent,
          content: textDraft,
          truncated: false,
          etag: newEtag ?? previousTextContent.etag ?? "",
        };
      });
      toast.success(t("file_preview.text.saved"));
    },
    onError: (e) => {
      const message =
        e instanceof APIError && e.code === 412
          ? t("file_preview.text.changed")
          : errorToString(e);
      toast.error(message);
    },
  });

  const handleDownload = async () => {
    handleDownloadFile?.(effectiveCurrentFile);
  };

  // Render the appropriate viewer based on file category
  const renderViewer = () => {
    const viewerKind = resolvePreviewViewerKind({
      currentFile,
      effectiveCurrentFile,
      isResolvingCurrentFile,
      hasResolveError: resolvedPreviewQuery.isError,
      useTextViewer,
      shouldRenderWopi,
    });

    switch (viewerKind) {
      case "empty":
        return <div>{t("file_preview.unsupported.title")}</div>;
      case "suspicious":
        return <SuspiciousPreview handleDownload={handleDownload} />;
      case "resolving":
        return <div>{t("file_preview.wopi.loading")}</div>;
      case "resolve_error":
        return (
          <div>
            <div>{errorToString(resolvedPreviewQuery.error)}</div>
            <Button variant="tertiary" onClick={() => resolvedPreviewQuery.refetch()}>
              {t("common.retry")}
            </Button>
          </div>
        );
      case "unsupported_kind":
      case "missing_url":
        return (
          <NotSupportedPreview
            title={t("file_preview.unavailable.title")}
            description={t("file_preview.unavailable.description")}
            file={effectiveCurrentFile!}
            onDownload={handleDownload}
          />
        );
      case "text":
        return (
          <TextPreview
            value={textDraft}
            onChange={setTextDraft}
            filename={currentFilename}
            isEditable={isEditingText && canEditText}
            truncated={isTextTruncated}
            isLoading={textQuery.isLoading}
            error={textQuery.error}
            onRetry={() => textQuery.refetch()}
          />
        );
      case "wopi":
        if (source.renderWopiEditor) {
          return source.renderWopiEditor(
            effectiveCurrentFile!,
            onFileRename,
            handleDownloadFile ? handleDownload : undefined,
          );
        }
        return (
          <WopiEditor
            item={effectiveCurrentFile!}
            onFileRename={onFileRename}
            onDownload={handleDownloadFile ? handleDownload : undefined}
          />
        );
      case "unsupported_heic":
        return (
          <NotSupportedPreview
            title={t("file_preview.unsupported.heic_title")}
            description={t("file_preview.unsupported.description")}
            file={effectiveCurrentFile!}
            onDownload={handleDownload}
          />
        );
      case "image":
        return (
          <ImageViewer
            src={effectiveCurrentFile!.url_preview!}
            alt={effectiveCurrentFile!.title}
            className="file-preview-viewer"
          />
        );
      case "video":
        return (
          <div className="video-preview-viewer-container">
            <div className="video-preview-viewer">
              <VideoPlayer
                src={effectiveCurrentFile!.url_preview!}
                className="file-preview-viewer"
                controls={true}
              />
            </div>
          </div>
        );
      case "audio":
        return (
          <div className="video-preview-viewer-container">
            <div className="video-preview-viewer">
              <AudioPlayer
                src={effectiveCurrentFile!.url_preview!}
                title={effectiveCurrentFile!.title}
                className="file-preview-viewer"
              />
            </div>
          </div>
        );
      case "pdf":
        return (
          <div className="file-preview-pdf-container">
            <PreviewPdf src={effectiveCurrentFile!.url_preview!} />
          </div>
        );
      case "archive":
        if (source.renderArchiveViewer) {
          return source.renderArchiveViewer(
            effectiveCurrentFile!,
            handleDownloadFile ? handleDownload : undefined,
          );
        }
        return (
          <ArchiveViewer
            archiveItem={{
              id: effectiveCurrentFile!.id,
              title: effectiveCurrentFile!.title,
              size: effectiveCurrentFile!.size,
              mimetype: effectiveCurrentFile!.mimetype,
              url: effectiveCurrentFile!.stream_url ?? effectiveCurrentFile!.url,
            }}
            archiveDetailsItemId={effectiveCurrentFile!.id}
            onDownloadArchive={handleDownloadFile ? handleDownload : undefined}
          />
        );
      case "unsupported":
      default:
        return (
          <NotSupportedPreview
            file={effectiveCurrentFile!}
            onDownload={handleDownload}
          />
        );
    }
  };

  useEffect(() => {
    if (openedFileId) {
      const index = data.findIndex((file) => file.id === openedFileId);
      const newIndex = index > -1 ? index : -1;
      setCurrentIndex(newIndex);
    } else {
      setCurrentIndex(-1);
    }
  }, [openedFileId]);

  useEffect(() => {
    if (!isOpen || !currentFile) {
      return;
    }
    onChangeFile?.(currentFile);
    if (!effectiveCurrentFile) {
      return;
    }
    posthog.capture("file_preview_opened", {
      id: effectiveCurrentFile.id,
      size: effectiveCurrentFile.size,
      mimetype: effectiveCurrentFile.mimetype,
    });
  }, [isOpen, currentFile, effectiveCurrentFile, onChangeFile]);

  if (!isOpen || !currentFile) {
    return null;
  }

  return (
    <Modal isOpen={isOpen} onClose={() => onClose?.()} size={ModalSize.FULL}>
      <div data-testid="file-preview">
        <div
          className={`file-preview-container ${
            isSidebarOpen ? "sidebar-open" : ""
          }`}
        >
          <div className="file-preview-header">
            <div className="file-preview-header__content">
              <div className="file-preview-header__content-left">
                {!hideCloseButton && (
                  <Button
                    variant="tertiary"
                    size="small"
                    onClick={onClose}
                    data-testid="file-preview-close"
                    icon={<Icon name="close" />}
                  />
                )}

                <div className="file-preview-title">
                  <FileIcon
                    file={effectiveCurrentFile ?? currentFile}
                    type="mini"
                    size="small"
                  />
                  <h1 className="file-preview-title">
                    {effectiveCurrentFile?.title || title}
                  </h1>
                </div>
              </div>
              <div className="file-preview-header__content-center">
                {!hideNav && (
                  <FilePreviewNav
                    currentIndex={currentIndex}
                    totalFiles={data.length}
                    onPrevious={() => setCurrentIndex(currentIndex - 1)}
                    onNext={() => setCurrentIndex(currentIndex + 1)}
                  />
                )}
              </div>
              <div className="file-preview-header__content-right">
                <TextPreviewHeaderActions
                  useTextViewer={useTextViewer}
                  isTextDirty={isTextDirty}
                  isEditingText={isEditingText}
                  isTextReadOnly={isTextReadOnly}
                  textEncoding={textEncoding}
                  canUpdateText={canUpdateText}
                  isTextTruncated={isTextTruncated}
                  textLoading={textQuery.isLoading}
                  textError={Boolean(textQuery.error)}
                  canEditText={canEditText}
                  isSavingText={saveTextMutation.isPending}
                  onStartEditing={() => setIsEditingText(true)}
                  onCancelEditing={() => {
                    setTextDraft(textBase);
                    setIsEditingText(false);
                  }}
                  onSave={() => saveTextMutation.mutate()}
                />
                {headerRightContent}
                {handleDownloadFile && (
                  <Button
                    variant="tertiary"
                    onClick={handleDownload}
                    icon={
                      <Icon type={IconType.OUTLINED} name={"file_download"} />
                    }
                  />
                )}

                <Button
                  variant="tertiary"
                  onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                  icon={<Icon name={"info_outline"} />}
                />
              </div>
            </div>
          </div>
          <div className="file-preview-content">
            <div className="file-preview-main">{renderViewer()}</div>

            <div
              className={`file-preview-sidebar ${isSidebarOpen ? "open" : ""}`}
            >
              {sidebarContent}
            </div>
          </div>
        </div>
      </div>
    </Modal>
  );
};

type TextPreviewHeaderActionsProps = {
  useTextViewer: boolean;
  isTextDirty: boolean;
  isEditingText: boolean;
  isTextReadOnly: boolean;
  textEncoding: string;
  canUpdateText: boolean;
  isTextTruncated: boolean;
  textLoading: boolean;
  textError: boolean;
  canEditText: boolean;
  isSavingText: boolean;
  onStartEditing: () => void;
  onCancelEditing: () => void;
  onSave: () => void;
};

const TextPreviewHeaderActions = ({
  useTextViewer,
  isTextDirty,
  isEditingText,
  isTextReadOnly,
  textEncoding,
  canUpdateText,
  isTextTruncated,
  textLoading,
  textError,
  canEditText,
  isSavingText,
  onStartEditing,
  onCancelEditing,
  onSave,
}: TextPreviewHeaderActionsProps) => {
  const { t } = useTranslation();

  if (!useTextViewer) {
    return null;
  }

  return (
    <>
      {isTextDirty && (
        <span className="file-preview-text-dirty">
          {t("file_preview.text.dirty")}
        </span>
      )}
      {!isEditingText ? (
        <>
          {isTextReadOnly && (
            <Tooltip
              content={t("file_preview.text.read_only_hint", {
                encoding: textEncoding,
              })}
            >
              <div>
                <button
                  type="button"
                  data-testid="text-readonly-info"
                  className="file-preview-text-readonly-info"
                  aria-label={t("file_preview.text.read_only_aria")}
                  onClick={() =>
                    toast.info(
                      t("file_preview.text.read_only_hint", {
                        encoding: textEncoding,
                      }),
                    )
                  }
                >
                  <Icon name="error_outline" />
                </button>
              </div>
            </Tooltip>
          )}
          <Button
            variant="tertiary"
            disabled={
              !canUpdateText || isTextTruncated || isTextReadOnly || textLoading || textError
            }
            onClick={onStartEditing}
          >
            {t("file_preview.text.edit")}
          </Button>
        </>
      ) : (
        <>
          <Button variant="tertiary" onClick={onCancelEditing}>
            {t("common.cancel")}
          </Button>
          <Button
            variant="tertiary"
            disabled={!canEditText || isTextTruncated || !isTextDirty || isSavingText}
            onClick={onSave}
          >
            {t("file_preview.text.save")}
          </Button>
        </>
      )}
    </>
  );
};

interface FilePreviewNavProps {
  currentIndex: number;
  totalFiles: number;
  onPrevious: () => void;
  onNext: () => void;
}

export const FilePreviewNav: React.FC<FilePreviewNavProps> = ({
  currentIndex,
  totalFiles,
  onPrevious,
  onNext,
}) => {
  if (totalFiles === 1) {
    return null;
  }
  return (
    <div className="file-preview-nav" data-testid="file-preview-nav">
      <Button
        variant="tertiary"
        onClick={onPrevious}
        disabled={currentIndex === 0}
        icon={<Icon name="arrow_back" />}
      />
      <span className="file-preview-nav__count">
        {currentIndex + 1} / {totalFiles}
      </span>
      <Button
        variant="tertiary"
        onClick={onNext}
        disabled={currentIndex === totalFiles - 1}
        icon={<Icon name="arrow_forward" />}
      />
    </div>
  );
};
