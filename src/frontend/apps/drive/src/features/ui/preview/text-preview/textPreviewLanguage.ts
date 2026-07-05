import { loadLanguage } from "@uiw/codemirror-extensions-langs";
import type { Extension } from "@codemirror/state";

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

export const getTextPreviewExtensionFromFilename = (
  filename?: string | null,
): string | null => {
  if (!filename) {
    return null;
  }
  const parts = filename.split(".");
  if (parts.length <= 1) {
    return null;
  }
  return parts.pop()?.toLowerCase() ?? null;
};

export const resolveTextPreviewExtensions = (
  filename?: string | null,
): Extension[] => {
  const ext = getTextPreviewExtensionFromFilename(filename);
  if (!ext) return [];
  const languageName = EXT_TO_LANGUAGE[ext];
  if (!languageName) return [];
  const lang = loadLanguage(languageName as Parameters<typeof loadLanguage>[0]);
  return lang ? [lang] : [];
};
