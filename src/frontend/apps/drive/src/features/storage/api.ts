import { useQuery } from "@tanstack/react-query";
import { fetchAPI } from "@/features/api/fetchApi";
import { Item, MountVirtualEntry } from "@/features/drivers/types";
import { jsonToItem } from "@/features/drivers/implementations/StandardDriver";
import { entryToMountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";

export type StoragePage<T> = {
  count: number;
  next: string | null;
  results: T[];
};
export type StorageSpace = {
  id: string;
  name: string;
  updated_at: string;
  roots: {
    id: string;
    title: string;
    updated_at: string;
    abilities?: Partial<Item["abilities"]>;
  }[];
  state: "ready" | "maintenance" | "index_pending";
  inventory_updated_at: string | null;
  usage: {
    used: number;
    reserved: number;
    limit: number | null;
    growth_blocked: boolean;
    policy_applied_at: string | null;
  };
};
export type StorageResource = {
  abilities?: Record<string, boolean>;
  id: string;
  space: string;
  title: string;
  kind: "file" | "folder" | "docs";
  size: number;
  adapter:
    | { kind: "item"; item: Item }
    | {
        kind: "mount";
        mount_id: string;
        path: string;
        entry: MountVirtualEntry;
        capabilities: Record<string, boolean>;
      };
};

export const storageRequest = async <T>(
  path: string,
  init?: Parameters<typeof fetchAPI>[1],
): Promise<T> => {
  const result = await fetchAPI(path, init);
  return result.status === 204 ? (undefined as T) : result.json();
};

export const resourceHref = (id: string, space?: string) =>
  `/explorer/resources/${encodeURIComponent(id)}${space ? `?space=${encodeURIComponent(space)}` : ""}`;

export const getResource = (id: string, space?: string) =>
  storageRequest<StorageResource>(`resources/${encodeURIComponent(id)}/`, {
    params: space ? { space } : {},
  });

export const useStorageResource = (id?: string, space?: string) =>
  useQuery({
    queryKey: ["storage", "resource", id, space],
    queryFn: () => getResource(id!, space),
    enabled: Boolean(id),
    refetchOnWindowFocus: true,
  });

export const resourceItem = (resource: StorageResource): Item =>
  resource.adapter.kind === "item"
    ? jsonToItem(resource.adapter.item)
    : {
        ...entryToMountExplorerItem(
          resource.adapter.mount_id,
          resource.adapter.entry,
          resource.title,
        ),
        title: resource.title,
      };

export const resolveLegacyMount = (mountId: string, path: string) =>
  storageRequest<{ id: string; space: string; href: string }>(
    "resources/resolve-legacy/",
    {
      params: { mount_id: mountId, path },
    },
  );

export type ConnectionChoice = {
  id: string;
  name: string;
  family: "s3" | "mount";
};
export type Configuration = {
  connections_manage: boolean;
  spaces_create: boolean;
  spaces_manage: boolean;
  organization: string;
  connections: ConnectionChoice[];
  quota_url: string;
  certificate_authorities: string[];
};

export const useStorageAdministration = () =>
  useQuery({
    queryKey: ["storage", "administration"],
    queryFn: () =>
      storageRequest<Configuration>("storage-spaces-admin/configuration/"),
    staleTime: 30000,
  });
