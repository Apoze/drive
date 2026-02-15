import dynamic from "next/dynamic";
import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { loadLanguage } from "@uiw/codemirror-extensions-langs";
import type { Extension } from "@codemirror/state";

import { getExtensionFromName } from "@/features/explorer/utils/utils";
import { errorToString } from "@/features/api/APIError";

const CodeMirror = dynamic(
  () => import("@uiw/react-codemirror").then((mod) => mod.default),
  { ssr: false },
);

const EXT_TO_LANGUAGE: Record<string, string> = {
  js: "javascript",
  jsx: "jsx",
  ts: "typescript",
  tsx: "tsx",
  json: "json",
  md: "markdown",
  yml: "yaml",
  yaml: "yaml",
  xml: "xml",
  html: "html",
  css: "css",
  scss: "scss",
  py: "python",
  sql: "sql",
  sh: "shell",
  bash: "shell",
  zsh: "shell",
  ini: "properties",
  conf: "properties",
  env: "properties",
  toml: "toml",
};

const languageExtensionsForFilename = (filename?: string | null): Extension[] => {
  const ext = getExtensionFromName(filename ?? "")?.toLowerCase();
  if (!ext) return [];
  const languageName = EXT_TO_LANGUAGE[ext];
  if (!languageName) return [];
  const lang = loadLanguage(languageName);
  return lang ? [lang] : [];
};

type TextPreviewProps = {
  value: string;
  onChange: (next: string) => void;
  filename?: string;
  isEditable: boolean;
  truncated: boolean;
  isLoading: boolean;
  error?: unknown;
  onRetry?: () => void;
};

export const TextPreview = ({
  value,
  onChange,
  filename,
  isEditable,
  truncated,
  isLoading,
  error,
  onRetry,
}: TextPreviewProps) => {
  const { t } = useTranslation();
  const extensions = useMemo(
    () => languageExtensionsForFilename(filename),
    [filename],
  );

  if (isLoading) {
    return <div className="text-preview__state">{t("file_preview.text.loading")}</div>;
  }

  if (error) {
    return (
      <div className="text-preview__state">
        <div>{errorToString(error)}</div>
        {onRetry && (
          <Button variant="tertiary" onClick={onRetry}>
            {t("common.retry")}
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="text-preview">
      {truncated && (
        <div className="text-preview__banner">
          {t("file_preview.text.large_file")}
        </div>
      )}
      <div className="text-preview__editor">
        <CodeMirror
          value={value}
          height="100%"
          extensions={extensions}
          editable={isEditable && !truncated}
          onChange={(next) => {
            if (isEditable && !truncated) {
              onChange(next);
            }
          }}
        />
      </div>
    </div>
  );
};

