import React from "react";
import { useTranslation } from "react-i18next";
import { FilePreviewType } from "../files-preview/FilesPreview";

import { Button } from "@gouvfr-lasuite/cunningham-react";
import { Icon, IconType } from "@gouvfr-lasuite/ui-kit";
import { FileIcon } from "@/features/explorer/components/icons/ItemIcon";
import { useCallback } from "react";

interface ErrorPreviewProps {
  file: FilePreviewType;
  onDownload?: () => void;
}

export const ErrorPreview = ({ file, onDownload }: ErrorPreviewProps) => {
  const { t } = useTranslation();

  const handleDownload = useCallback(() => {
    onDownload?.();
  }, [onDownload]);

  return (
    <div className="file-preview-error">
      <div className="file-preview-error__icon">
        <FileIcon file={file} size="xlarge" />
      </div>
      <div className="file-preview-error__title">
        {t("file_preview.error.title")}
      </div>
      <div className="file-preview-error__description">
        {t("file_preview.error.description")}
      </div>

      {onDownload && (
        <Button
          variant="bordered"
          className="file-preview-error__download-button"
          icon={<Icon name="file_download" type={IconType.OUTLINED} size={16} />}
          onClick={handleDownload}
        >
          {t("file_preview.unsupported.download")}
        </Button>
      )}
    </div>
  );
};
