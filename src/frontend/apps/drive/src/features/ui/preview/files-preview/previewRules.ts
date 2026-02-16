import { getMimeCategory, MimeCategory } from "@/features/explorer/utils/mimeTypes";
import { getExtensionFromName } from "@/features/explorer/utils/utils";

const TEXT_LIKE_MIME_ALLOWLIST = new Set([
  "application/json",
  "application/xml",
  "application/x-yaml",
  "application/yaml",
  "application/toml",
  "application/x-ini",
]);

const TEXT_EXT_ALLOWLIST = new Set([
  "txt",
  "md",
  "log",
  "csv",
  "tsv",
  "json",
  "yaml",
  "yml",
  "xml",
  "ini",
  "conf",
  "env",
  "inf",
  "py",
  "js",
  "jsx",
  "ts",
  "tsx",
  "sql",
  "sh",
  "bash",
  "zsh",
  "fish",
  "toml",
  "properties",
  "gitignore",
  "dockerfile",
  "makefile",
]);

const TEXT_EXT_DENYLIST = new Set([
  "sys",
  "exe",
  "dll",
  "bin",
  "dat",
  "so",
  "dylib",
]);

const ARCHIVE_CONTAINER_EXT = new Set(["zip", "tar"]);
const ARCHIVE_MULTI_EXT = [
  "tar.gz",
  "tgz",
  "tar.bz2",
  "tbz",
  "tbz2",
  "tar.xz",
  "txz",
];
const COMPRESSION_SINGLE_EXT = new Set(["gz", "bz2", "xz"]);

const normalizeMime = (mimetype: string) =>
  String(mimetype ?? "")
    .split(";", 1)[0]
    .trim()
    .toLowerCase();

export const getTextKey = (filename: string) => {
  const lower = filename.toLowerCase();
  const ext = getExtensionFromName(filename)?.toLowerCase();
  if (ext) return ext;
  if (lower === "dockerfile") return "dockerfile";
  if (lower === "makefile") return "makefile";
  return null;
};

export const isTextEligibleByRules = (mimetype: string, filename: string) => {
  const mime = normalizeMime(mimetype);
  const textKey = getTextKey(filename);
  if (mime.startsWith("text/")) return true;
  if (TEXT_LIKE_MIME_ALLOWLIST.has(mime)) return true;
  if (textKey === null) return false;
  if (TEXT_EXT_DENYLIST.has(textKey)) return false;
  return (
    textKey !== null && TEXT_EXT_ALLOWLIST.has(textKey)
  );
};

const isSupportedArchiveByFilename = (filename: string) => {
  const lower = (filename ?? "").toLowerCase();
  for (const multi of ARCHIVE_MULTI_EXT) {
    if (lower.endsWith(`.${multi}`)) return true;
  }
  const ext = getExtensionFromName(lower)?.toLowerCase();
  if (!ext) return false;
  if (ARCHIVE_CONTAINER_EXT.has(ext)) return true;
  if (COMPRESSION_SINGLE_EXT.has(ext)) return false;
  return false;
};

export const isArchiveEligibleByRules = (mimetype: string, filename: string) => {
  if (isSupportedArchiveByFilename(filename)) return true;
  const mime = normalizeMime(mimetype);
  return mime === "application/zip" || mime === "application/x-tar";
};

export const getPreviewMimeCategory = (mimetype: string, filename: string) => {
  const extension = getExtensionFromName(filename);
  if (isArchiveEligibleByRules(mimetype, filename)) {
    return MimeCategory.ARCHIVE;
  }
  const category = getMimeCategory(mimetype, extension);
  // Enforce allowlist-only archive routing for preview: never open the archive viewer
  // based on generic/binary MIME alone.
  if (category === MimeCategory.ARCHIVE) {
    return MimeCategory.OTHER;
  }
  return category;
};
