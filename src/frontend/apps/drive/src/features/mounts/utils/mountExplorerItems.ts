import { getOrigin } from "@/features/api/utils";
import {
  Item,
  ItemType,
  ItemUploadState,
  LinkReach,
  LinkRole,
  MountDiscovery,
  MountEntryType,
  MountVirtualEntry,
} from "@/features/drivers/types";
import { getExtensionFromName } from "@/features/explorer/utils/utils";

export type MountExplorerItemMeta = {
  mountId: string;
  normalizedPath: string;
  entryType: MountEntryType;
  mountTitle: string;
  provider?: string;
  isMountRoot?: boolean;
  abilities?: MountVirtualEntry["abilities"];
};

export type MountExplorerItem = Item & {
  mountMeta: MountExplorerItemMeta;
};

const DEFAULT_CREATOR = {
  id: "mount",
  full_name: "Mount",
  short_name: "MT",
};

const EMPTY_ABILITIES = {
  accesses_manage: false,
  accesses_view: false,
  children_create: false,
  children_list: false,
  destroy: false,
  favorite: false,
  invite_owner: false,
  link_configuration: false,
  media_auth: false,
  move: false,
  link_select_options: {
    [LinkReach.RESTRICTED]: null,
    [LinkReach.AUTHENTICATED]: null,
    [LinkReach.PUBLIC]: null,
  },
  partial_update: false,
  restore: false,
  retrieve: false,
  tree: false,
  update: false,
  upload_ended: false,
};

const MOUNT_MIME_BY_EXTENSION: Record<string, string> = {
  pdf: "application/pdf",
  png: "image/png",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  gif: "image/gif",
  webp: "image/webp",
  svg: "image/svg+xml",
  mp4: "video/mp4",
  webm: "video/webm",
  mp3: "audio/mpeg",
  wav: "audio/wav",
  ogg: "audio/ogg",
  txt: "text/plain",
  md: "text/markdown",
  csv: "text/csv",
  css: "text/css",
  html: "text/html",
  js: "text/javascript",
  ts: "text/typescript",
  json: "application/json",
  xml: "application/xml",
  yml: "application/yaml",
  yaml: "application/yaml",
  sh: "text/x-shellscript",
  py: "text/x-python",
  sql: "text/plain",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  odt: "application/vnd.oasis.opendocument.text",
  ods: "application/vnd.oasis.opendocument.spreadsheet",
  odp: "application/vnd.oasis.opendocument.presentation",
  zip: "application/zip",
};

export const getMountTitle = (mount: Pick<MountDiscovery, "provider" | "display_name">) => {
  if (mount.provider.toLowerCase() === "smb") {
    return "SMB";
  }
  return mount.display_name || mount.provider.toUpperCase();
};

const guessMountMimeType = (name: string) => {
  const extension = getExtensionFromName(name)?.toLowerCase();
  if (!extension) {
    return "application/octet-stream";
  }
  return MOUNT_MIME_BY_EXTENSION[extension] ?? "application/octet-stream";
};

const buildMountDownloadUrl = (mountId: string, path: string) => {
  const origin = getOrigin();
  const query = new URLSearchParams({ path });
  const prefix = origin || "";
  return `${prefix}/api/v1.0/mounts/${mountId}/download/?${query.toString()}`;
};

const buildMountPreviewUrl = (mountId: string, path: string) => {
  const origin = getOrigin();
  const query = new URLSearchParams({ path });
  const prefix = origin || "";
  return `${prefix}/api/v1.0/mounts/${mountId}/preview/?${query.toString()}`;
};

const buildBaseItem = ({
  id,
  title,
  filename,
  type,
  updatedAt,
  size,
  url,
  urlPreview,
  mimetype,
  childrenCreate,
  childrenList,
  retrieve,
  canUpdate,
  mountMeta,
}: {
  id: string;
  title: string;
  filename: string;
  type: ItemType;
  updatedAt: Date;
  size?: number;
  url?: string;
  urlPreview?: string;
  mimetype?: string;
  childrenCreate?: boolean;
  childrenList?: boolean;
  retrieve?: boolean;
  canUpdate?: boolean;
  mountMeta: MountExplorerItemMeta;
}): MountExplorerItem => {
  return {
    id,
    title,
    filename,
    creator: DEFAULT_CREATOR,
    type,
    ancestors_link_reach: null,
    ancestors_link_role: null,
    computed_link_reach: null,
    computed_link_role: null,
    upload_state: ItemUploadState.READY,
    updated_at: updatedAt,
    description: "",
    created_at: updatedAt,
    path: mountMeta.normalizedPath,
    url,
    url_preview: urlPreview,
    size,
    mimetype,
    link_reach: LinkReach.RESTRICTED,
    link_role: LinkRole.READER,
    abilities: {
      ...EMPTY_ABILITIES,
      children_create: Boolean(childrenCreate),
      children_list: Boolean(childrenList),
      retrieve: Boolean(retrieve),
      update: Boolean(canUpdate),
    },
    mountMeta,
  } as MountExplorerItem;
};

export const discoveryToMountExplorerItem = (
  mount: MountDiscovery,
): MountExplorerItem => {
  const mountTitle = getMountTitle(mount);
  return buildBaseItem({
    id: `mount-root:${mount.mount_id}`,
    title: mountTitle,
    filename: mountTitle,
    type: ItemType.FOLDER,
    updatedAt: new Date(),
    childrenCreate: false,
    childrenList: true,
    retrieve: true,
    mountMeta: {
      mountId: mount.mount_id,
      normalizedPath: "/",
      entryType: "folder",
      mountTitle,
      provider: mount.provider,
      isMountRoot: true,
    },
  });
};

export const entryToMountExplorerItem = (
  mountId: string,
  entry: MountVirtualEntry,
  mountTitle: string,
  provider?: string,
): MountExplorerItem => {
  const isFolder = entry.entry_type === "folder";
  const mimetype = isFolder ? undefined : guessMountMimeType(entry.name);
  return buildBaseItem({
    id: `mount-entry:${mountId}:${entry.normalized_path}`,
    title: entry.name,
    filename: entry.name,
    type: isFolder ? ItemType.FOLDER : ItemType.FILE,
    updatedAt: entry.modified_at ? new Date(entry.modified_at) : new Date(),
    size: entry.size ?? undefined,
    url:
      !isFolder && entry.abilities.download
        ? buildMountDownloadUrl(mountId, entry.normalized_path)
        : undefined,
    urlPreview:
      !isFolder && entry.abilities.preview
        ? buildMountPreviewUrl(mountId, entry.normalized_path)
        : undefined,
    mimetype,
    childrenCreate: isFolder && entry.abilities.upload,
    childrenList: isFolder && entry.abilities.children_list,
    retrieve: !isFolder ? entry.abilities.download : true,
    canUpdate: false,
    mountMeta: {
      mountId,
      normalizedPath: entry.normalized_path,
      entryType: entry.entry_type,
      mountTitle,
      provider,
      abilities: entry.abilities,
    },
  });
};

export const getMountExplorerMeta = (item: Item) => {
  return (item as MountExplorerItem).mountMeta;
};
