import { useSelectedItems, useSetSelectedItems } from "@/features/explorer/stores/selectionStore";
import { ColumnPreferencesProvider } from "@/features/explorer/hooks/useColumnPreferences";
import { useAuth } from "@/features/auth/Auth";
import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { useQuery } from "@tanstack/react-query";
import { Button, Input } from "@gouvfr-lasuite/cunningham-react";
import { useTranslation } from "react-i18next";
import { AppExplorer } from "@/features/explorer/components/app-view/AppExplorer";
import { getSdkLayout } from "@/features/layouts/components/sdk/SdkLayout";
import { discoveryToMountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";
import { Item } from "@/features/drivers/types";
import { DefaultRoute } from "@/utils/defaultRoutes";
import {
  getResource, resourceHref, resourceItem, storageRequest,
  StoragePage, StorageResource, StorageSpace,
} from "@/features/storage/api";

type Folder = { id: string; space: string; title: string };

export default function SuiteFilePicker({ consumer = "messages" }: { consumer?: "messages" | "projects" }) {
  const { t } = useTranslation();
  const router = useRouter();
  const { user } = useAuth();
  const [trail, setTrail] = useState<Folder[]>([]);
  const [offset, setOffset] = useState(0);
  const [filename, setFilename] = useState("");
  const [selected, setSelected] = useState<StorageResource>();
  const selectedItems = useSelectedItems();
  const setSelectedItems = useSetSelectedItems();
  const current = trail.at(-1);
  const folderMode = router.query.mode === "folder";
  const config = useQuery({
    queryKey: ["suite-picker-config"],
    queryFn: () => storageRequest<{ MESSAGES_PUBLIC_URL: string; PROJECTS_PUBLIC_URL: string }>("config/"),
  });
  const target = useQuery({
    queryKey: ["storage", "resource", current?.id, current?.space],
    queryFn: () => getResource(current!.id, current!.space),
    enabled: Boolean(user && current),
  });
  const listing = useQuery({
    queryKey: ["suite-picker", consumer, current?.id, current?.space, offset],
    enabled: Boolean(user),
    queryFn: async () => {
      if (current) {
        const page = await storageRequest<StoragePage<StorageResource>>(`resources/${current.id}/children/`, {
          params: { space: current.space, offset, limit: 50 },
        });
        return { next: page.next, resources: page.results, folders: [] as Folder[],
          items: page.results.map((resource) => ({ ...resourceItem(resource), id: resource.id })) };
      }
      const page = await storageRequest<StoragePage<StorageSpace>>("spaces/", { params: { offset, limit: 50 } });
      const folders = page.results.flatMap((space) => space.roots.map((root) => ({
        id: root.id, space: space.id, title: space.roots.length > 1 ? `${space.name} — ${root.title}` : space.name,
      })));
      return { next: page.next, resources: [] as StorageResource[], folders,
        items: folders.map((folder) => ({ ...discoveryToMountExplorerItem({
          mount_id: folder.id, display_name: folder.title, provider: "virtual", capabilities: {},
        }), id: folder.id })) };
    },
  });
  useEffect(() => {
    const last = selectedItems.at(-1);
    if (last) setSelected(listing.data?.resources.find(resource => resource.id === last.id));
  }, [selectedItems, listing.data]);
  const navigate = (next: Folder[]) => { setTrail(next); setOffset(0); setSelected(undefined); setSelectedItems([]); };
  const open = (item: Item) => {
    const resource = listing.data?.resources.find((entry) => entry.id === item.id);
    const folder = listing.data?.folders.find((entry) => entry.id === item.id);
    if (folder) navigate([...trail, folder]);
    else if (resource?.kind === "folder") navigate([...trail, resource]);
    else if (!folderMode) setSelected(resource);
  };
  const configuredUrl = consumer === "projects" ? config.data?.PROJECTS_PUBLIC_URL : config.data?.MESSAGES_PUBLIC_URL;
  let targetOrigin = "";
  try { if (configuredUrl) targetOrigin = new URL(configuredUrl).origin; } catch { /* Invalid registration stays closed. */ }
  const allowed = Boolean(targetOrigin && router.query.origin === targetOrigin);
  const choose = (action: "folder" | "link" | "copy") => {
    const resource = action === "folder" ? target.data : selected;
    if (!resource || !allowed || !window.opener) return;
    window.opener.postMessage({
      type: "suite-drive-selection", request: router.query.request,
      selection: { resource: resource.id, space: resource.space, name: resource.title,
        kind: resource.kind, size: resource.size ?? 0, action, filename: filename.trim(),
        url: window.location.origin + resourceHref(resource.id, resource.space) },
    }, targetOrigin);
    window.close();
  };
  if (!user || config.isPending) return <p role="status">{t("storage.loading")}</p>;
  if (!allowed || typeof router.query.request !== "string" || !/^[a-f0-9-]{36}$/.test(router.query.request)) {
    return <p role="alert">{t("messages_picker.invalid_request")}</p>;
  }
  return <div className="sdk__explorer__page messages-picker">
    <nav style={{ display: "flex", flexWrap: "wrap", gap: 8 }} aria-label={t("storage.transfers.destination")}>
      <Button variant="tertiary" onClick={() => navigate([])}>{t("storage.spaces")}</Button>
      {trail.map((folder, index) => <Button variant="tertiary" key={`${folder.space}:${folder.id}`} onClick={() => navigate(trail.slice(0, index + 1))}>{folder.title}</Button>)}
    </nav>
    {listing.isError && <p role="alert">{t("storage.load_error")}</p>}
    <div className="sdk__explorer" style={{ minHeight: 0 }}>
    <AppExplorer disableAreaSelection gridHeader={<></>} viewConfigKey={DefaultRoute.MY_FILES} childrenItems={listing.data?.items}
      isLoading={listing.isPending} showFilters={false} disableDefaultContextMenu
      disableItemDragAndDrop gridActionsCell={() => null} canSelect={item => !folderMode && item.type !== "folder"}
      onNavigate={({ item }) => open(item as Item)} onFileClick={open}
      selectionBarActions={null} isMinimalLayout />
    </div>
    {folderMode && <Input label={t("messages_picker.filename")} value={filename} maxLength={255} onChange={event => setFilename(event.target.value)} />}
    <div className="sdk__explorer__footer">
      <Button variant="tertiary" disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 50))}>{t("storage.transfers.previous")}</Button>
      <Button variant="tertiary" disabled={!listing.data?.next} onClick={() => setOffset(offset + 50)}>{t("storage.transfers.next")}</Button>
      {selected && <span>{selected.title}</span>}
      <Button variant="tertiary" onClick={() => window.close()}>{t("sdk.explorer.cancel")}</Button>
      {folderMode ? <Button disabled={!target.data?.abilities?.children_create && !target.data?.abilities?.upload} onClick={() => choose("folder")}>{t("messages_picker.folder")}</Button> : <>
        <Button disabled={!selected} onClick={() => choose("link")}>{t("messages_picker.link")}</Button>
        <Button disabled={!selected || (selected.kind === "docs" && !selected.abilities?.export)} onClick={() => choose("copy")}>{t(selected?.kind === "docs" ? "messages_picker.pdf" : "messages_picker.copy")}</Button>
      </>}
    </div>
    <p>{t("messages_picker.rights")}</p>
    <style jsx>{`
      .messages-picker :global(.explorer) { width: 100%; min-height: 0; }
      .messages-picker :global(.explorer__container) { width: 100%; }
      .messages-picker > p { padding: 0 24px; }
    `}</style>
  </div>;
}

SuiteFilePicker.getLayout = (page: React.ReactElement) => getSdkLayout(<ColumnPreferencesProvider>{page}</ColumnPreferencesProvider>, true);
