import { useSelectedItems, useSetSelectedItems } from "@/features/explorer/stores/selectionStore";
import { ColumnPreferencesProvider } from "@/features/explorer/hooks/useColumnPreferences";
import { login, useAuth } from "@/features/auth/Auth";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/router";
import { useQuery } from "@tanstack/react-query";
import { Button, Input } from "@gouvfr-lasuite/cunningham-react";
import { useTranslation } from "react-i18next";
import { AppExplorer } from "@/features/explorer/components/app-view/AppExplorer";
import { getSdkLayout } from "@/features/layouts/components/sdk/SdkLayout";
import { discoveryToMountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";
import { Item } from "@/features/drivers/types";
import { DefaultRoute } from "@/utils/defaultRoutes";
import { useTransferIntake } from "./useTransferIntake";
import { fetchAPI } from "@/features/api/fetchApi";
import { APIError } from "@/features/api/APIError";
import { chatCopy, CHAT_COPY_MAX_BYTES } from "./chatCopy";
import { ItemShareModalLauncher } from "@/features/explorer/components/itemShareModalLauncher";
import {
  resourceHref, resourceItem,
  StoragePage, StorageResource, StorageSpace,
} from "@/features/storage/api";

type Folder = { id: string; space: string; title: string };

export default function SuiteFilePicker({ consumer = "messages" }: { consumer?: "messages" | "projects" | "transfers" | "chat" }) {
  const { t } = useTranslation();
  const router = useRouter();
  const { user } = useAuth();
  const authenticationPending = useRef(false);
  const pickerRequest = async <T,>(path: string, init?: Parameters<typeof fetchAPI>[1]): Promise<T> => {
    try {
      const result = await fetchAPI(path, init, { redirectOn40x: false });
      return result.json();
    } catch (error) {
      if (error instanceof APIError && error.code === 401 && !authenticationPending.current) {
        authenticationPending.current = true;
        login(window.location.href);
      }
      throw error;
    }
  };
  const [trail, setTrail] = useState<Folder[]>([]);
  const [offset, setOffset] = useState(0);
  const [filename, setFilename] = useState("");
  const [selected, setSelected] = useState<StorageResource>();
  const [copying, setCopying] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const [mobileShare, setMobileShare] = useState<ShareData>();
  const [shareOpened, setShareOpened] = useState(false);
  const [sharing, setSharing] = useState<Item>();
  const selectedItems = useSelectedItems();
  const setSelectedItems = useSetSelectedItems();
  const current = trail.at(-1);
  const mobileMode = consumer === "chat" && router.query.mobile === "1";
  useEffect(() => { setMobileShare(undefined); setShareOpened(false); }, [selected?.id, selected?.space]);
  const folderMode = router.query.mode === "folder";
  const config = useQuery({
    queryKey: ["suite-picker-config"],
    queryFn: () => pickerRequest<{ MESSAGES_PUBLIC_URL: string; PROJECTS_PUBLIC_URL: string; TRANSFERS_PUBLIC_URL: string; CHAT_PUBLIC_URL: string; CHAT_PICKER_PUBLIC_URL: string }>("config/"),
  });
  useEffect(() => {
    if (!mobileMode || !config.data?.CHAT_PICKER_PUBLIC_URL) return;
    try {
      const destination = new URL(config.data.CHAT_PICKER_PUBLIC_URL);
      if (destination.protocol !== "https:" || destination.username || destination.password ||
          destination.origin === window.location.origin) return;
      const currentUrl = new URL(window.location.href);
      destination.pathname = currentUrl.pathname;
      destination.search = currentUrl.search;
      window.location.replace(destination.href);
    } catch { /* Invalid deployment URL leaves the current page available. */ }
  }, [mobileMode, config.data?.CHAT_PICKER_PUBLIC_URL]);
  const target = useQuery({
    queryKey: ["storage", "resource", current?.id, current?.space],
    queryFn: () => pickerRequest<StorageResource>(`resources/${current!.id}/`, { params: { space: current!.space } }),
    enabled: Boolean(user && current),
  });
  const listing = useQuery({
    queryKey: ["suite-picker", consumer, current?.id, current?.space, offset],
    enabled: Boolean(user),
    queryFn: async () => {
      if (current) {
        const page = await pickerRequest<StoragePage<StorageResource>>(`resources/${current.id}/children/`, {
          params: { space: current.space, offset, limit: 50 },
        });
        return { next: page.next, resources: page.results, folders: [] as Folder[],
          items: page.results.map((resource) => ({ ...resourceItem(resource), id: resource.id })) };
      }
      const page = await pickerRequest<StoragePage<StorageSpace>>("spaces/", { params: { offset, limit: 50 } });
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
  const configuredUrl = consumer === "chat" ? config.data?.CHAT_PUBLIC_URL : consumer === "transfers" ? config.data?.TRANSFERS_PUBLIC_URL
    : consumer === "projects" ? config.data?.PROJECTS_PUBLIC_URL : config.data?.MESSAGES_PUBLIC_URL;
  const choices = selectedItems.map(item => listing.data?.resources.find(resource => resource.id === item.id))
    .filter((resource): resource is StorageResource => Boolean(resource && resource.kind !== "folder"));
  const copies = choices.length ? choices : selected ? [selected] : [];
  let targetOrigin = "";
  try { if (configuredUrl) targetOrigin = new URL(configuredUrl).origin; } catch { /* Invalid registration stays closed. */ }
  const allowed = Boolean(targetOrigin && router.query.origin === targetOrigin);
  const intakeMode = ["transfers", "chat"].includes(consumer) && folderMode && router.query.intake === "1";
  const requestId = typeof router.query.request === "string" && /^[a-f0-9-]{36}$/.test(router.query.request)
    ? router.query.request : "";
  const chatPrincipal = typeof router.query.principal === "string" ? router.query.principal : "";
  const chatIdentity = useQuery({
    queryKey: ["chat-picker-identity", chatPrincipal],
    enabled: Boolean(consumer === "chat" && allowed && user && /^[a-f0-9-]{36}$/.test(chatPrincipal)),
    queryFn: () => pickerRequest<{ principal: string; link_origin: string }>("chat-files/", { headers: { "X-Suite-Principal": chatPrincipal } }),
    retry: false,
  });
  const intake = useTransferIntake(Boolean(intakeMode && allowed && user && (consumer !== "chat" || chatIdentity.isSuccess)), targetOrigin, requestId, consumer === "chat" ? chatPrincipal : undefined);
  useEffect(() => { if (intake.file) setFilename(intake.resume?.filename || intake.file.name); }, [intake.file, intake.resume]);
  useEffect(() => { if (intake.resume) setTrail([intake.resume]); }, [intake.resume]);
  useEffect(() => { if (intake.done) void listing.refetch(); }, [intake.done, listing.refetch]);
  const choose = async (action: "folder" | "link" | "copy") => {
    const resource = action === "folder" ? target.data : selected;
    if (!resource || !allowed || (!window.opener && !mobileMode) || copying) return;
    let attachment: { name: string; type: string; bytes: ArrayBuffer } | undefined;
    const principal = typeof router.query.principal === "string" ? router.query.principal : "";
    if (consumer === "chat") {
      setCopyError(false);
      setCopying(true);
      try {
        if (!/^[a-f0-9-]{36}$/.test(principal)) throw new Error("Invalid account");
        await pickerRequest("chat-files/", { headers: { "X-Suite-Principal": principal } });
        if (action === "copy") {
          const file = await chatCopy(resource, principal);
          if (mobileMode) setMobileShare({ files: [file], title: file.name });
          else attachment = { name: file.name, type: file.type, bytes: await file.arrayBuffer() };
        }
        else await pickerRequest("chat-files/", { method: "PATCH", headers: { "X-Suite-Principal": principal },
          body: JSON.stringify({ resource: resource.id, space: resource.space }) });
      } catch (error) {
        if (error instanceof APIError && error.code === 401) login(window.location.href);
        setCopyError(true);
        setCopying(false);
        return;
      }
      setCopying(false);
      if (mobileMode) {
        if (action === "link") setMobileShare({ title: resource.title,
          url: (chatIdentity.data?.link_origin || window.location.origin) + resourceHref(resource.id, resource.space) });
        setShareOpened(false);
        return;
      }
    }
    window.opener.postMessage({
      type: "suite-drive-selection", request: router.query.request,
      ...(consumer === "chat" ? { principal, file: attachment } : {}),
      ...(consumer === "transfers" && action === "copy" ? { selections: copies.map(entry => ({
        resource: entry.id, space: entry.space, name: entry.title, kind: entry.kind,
        size: entry.size ?? 0, action,
      })) } : {}),
      selection: { resource: resource.id, space: resource.space, name: resource.title,
        kind: resource.kind, size: resource.size ?? 0, action, filename: filename.trim(),
        url: window.location.origin + resourceHref(resource.id, resource.space) },
    }, targetOrigin, attachment ? [attachment.bytes] : []);
    window.close();
  };
  const shareOnDevice = async () => {
    if (!mobileShare) return;
    setCopyError(false);
    try {
      await navigator.share(mobileShare);
      setShareOpened(true);
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) setCopyError(true);
    }
  };
  const saveMobileSelection = async () => {
    if (!mobileShare) return;
    try {
      if (mobileShare.files?.[0]) {
        const url = URL.createObjectURL(mobileShare.files[0]);
        const link = document.createElement("a");
        link.href = url; link.download = mobileShare.files[0].name;
        document.body.appendChild(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
      } else if (mobileShare.url) await navigator.clipboard.writeText(mobileShare.url);
    } catch { setCopyError(true); }
  };
  if (!user || config.isPending) return <p role="status">{t("storage.loading")}</p>;
  if (!allowed || typeof router.query.request !== "string" || !/^[a-f0-9-]{36}$/.test(router.query.request)) {
    return <p role="alert">{t("messages_picker.invalid_request")}</p>;
  }
  return <div className="sdk__explorer__page messages-picker" data-mobile-ready={Boolean(mobileMode && mobileShare)}>
    <ItemShareModalLauncher isOpen={Boolean(sharing)} item={sharing} onClose={() => setSharing(undefined)} />
    <nav style={{ display: mobileMode && mobileShare ? "none" : "flex", flexWrap: "wrap", gap: 8, justifyContent: "flex-start", border: 0 }} aria-label={t("storage.transfers.destination")}>
      <Button color="neutral" variant="secondary" onClick={() => navigate([])}>{t("storage.spaces")}</Button>
      {trail.map((folder, index) => <Button color="neutral" variant="secondary" key={`${folder.space}:${folder.id}`} onClick={() => navigate(trail.slice(0, index + 1))}>{folder.title}</Button>)}
    </nav>
    {listing.isError && <p role="alert">{t("storage.load_error")}</p>}
    {copying && <p role="status">{t("chat_picker.copying")}</p>}
    {(copyError || chatIdentity.isError) && <p role="alert">{t("chat_picker.failed")}</p>}
    <div className="sdk__explorer" style={{ minHeight: 0 }}>
    <AppExplorer disableAreaSelection gridHeader={<></>} viewConfigKey={DefaultRoute.MY_FILES} childrenItems={listing.data?.items}
      isLoading={listing.isPending} showFilters={false} disableDefaultContextMenu
      disableItemDragAndDrop gridActionsCell={() => null} canSelect={item => !folderMode && item.type !== "folder"}
      onNavigate={({ item }) => open(item as Item)} onFileClick={open}
      selectionBarActions={<></>} isMinimalLayout />
    </div>
    {folderMode && <div style={{ padding: "8px 24px", flexShrink: 0 }}><Input label={t(intakeMode ? "transfer_intake.filename" : "messages_picker.filename")} value={filename} maxLength={255} disabled={intake.busy || intake.done} onChange={event => setFilename(event.target.value)} fullWidth /></div>}
    {intakeMode && <div style={{ padding: "8px 24px" }}>
      <p>{t(consumer === "chat" ? "chat_picker.save_notice" : "transfer_intake.notice")}</p>
      {intake.busy && <p role="status">{t("transfer_intake.progress", { percent: intake.progress })}</p>}
      {intake.done && <p role="status">{t("transfer_intake.done")}</p>}
      {intake.error && <p role="alert">{t(intake.error)}</p>}
      {intake.needsLogin && <Button onClick={() => login(window.location.href)}>{t("transfer_intake.login")}</Button>}
    </div>}
    <div className="sdk__explorer__footer">
      <div className="picker-actions">
      <Button color="neutral" variant="secondary" disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 50))}>{t("storage.transfers.previous")}</Button>
      <Button color="neutral" variant="secondary" disabled={!listing.data?.next} onClick={() => setOffset(offset + 50)}>{t("storage.transfers.next")}</Button>
      </div>
      {selected && <span className="picker-selection">{selected.title}</span>}
      <div className="picker-actions">
      <Button color="neutral" variant="secondary" onClick={() => intakeMode ? void intake.cancel() : mobileMode ? window.location.assign("apozechat://return") : window.close()}>{t(intake.done ? "transfer_intake.close" : "sdk.explorer.cancel")}</Button>
      {intake.done && intake.saved ? <Button onClick={() => window.open(resourceHref(intake.saved!.id, intake.saved!.space), "_blank", "noopener,noreferrer")}>{t("transfer_intake.open")}</Button> : folderMode ? <Button disabled={(!target.data?.abilities?.children_create && !target.data?.abilities?.upload) || (intakeMode && (!intake.file || intake.busy || intake.done))}
        onClick={() => intakeMode && target.data ? void intake.copy(target.data, filename) : choose("folder")}>{t(intakeMode ? "transfer_intake.save" : "messages_picker.folder")}</Button> : <>
        {consumer === "chat" && selected?.adapter.kind === "item" && selected.adapter.item.abilities?.accesses_view &&
          <Button color="neutral" variant="secondary" disabled={copying} onClick={() => setSharing(resourceItem(selected))}>{t("chat_picker.manage_access")}</Button>}
        {consumer !== "transfers" && <Button disabled={!selected || copying} onClick={() => void choose("link")}>{t(consumer === "chat" ? "chat_picker.link" : "messages_picker.link")}</Button>}
        <Button disabled={!selected || copying || (consumer === "chat" && selected.kind !== "docs" && (selected.size ?? 0) > CHAT_COPY_MAX_BYTES) || (consumer === "transfers" ? copies : [selected]).some(entry => entry.kind === "docs" && !entry.abilities?.export)} onClick={() => void choose("copy")}>{t((consumer === "transfers" ? copies.length > 0 && copies.every(entry => entry.kind === "docs") : selected?.kind === "docs") ? "messages_picker.pdf" : "messages_picker.copy")}{consumer === "transfers" && copies.length > 1 ? ` (${copies.length})` : ""}</Button>
      </>}
      </div>
    </div>
    {mobileMode && mobileShare && <section className="mobile-share" aria-label={t("chat_picker.device_share")}>
      <p>{mobileShare.title}</p>
      <p>{t("chat_picker.device_notice")}</p>
      <div className="picker-actions">
        {typeof navigator !== "undefined" && navigator.canShare?.(mobileShare) &&
          <Button onClick={() => void shareOnDevice()}>{t("chat_picker.device_share")}</Button>}
        <Button color="neutral" variant="secondary" onClick={() => void saveMobileSelection()}>
          {t(mobileShare.files ? "chat_picker.device_save" : "chat_picker.device_copy")}
        </Button>
      </div>
      <div className="picker-actions">
        <Button color="neutral" variant="secondary" onClick={() => { setMobileShare(undefined); setShareOpened(false); }}>{t("chat_picker.device_choose")}</Button>
        <Button color="neutral" variant="secondary" onClick={() => window.location.assign("apozechat://return")}>{t("chat_picker.device_return")}</Button>
      </div>
      {shareOpened && <p role="status">{t("chat_picker.device_opened")}</p>}
    </section>}
    {!intakeMode && <p>{t(consumer === "chat" ? "chat_picker.rights" : consumer === "transfers" ? "messages_picker.transfers_rights" : "messages_picker.rights")}</p>}
    <style jsx>{`
      .messages-picker { flex: 1; height: auto; min-height: 0; }
      .messages-picker[data-mobile-ready="true"] > nav,
      .messages-picker[data-mobile-ready="true"] > .sdk__explorer,
      .messages-picker[data-mobile-ready="true"] > .sdk__explorer__footer { display: none; }
      .mobile-share { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 12px; padding: 8px 24px; flex-shrink: 0; }
      .mobile-share p { margin: 4px 0 8px; overflow-wrap: anywhere; }
      .messages-picker nav { padding: 12px 24px; flex-shrink: 0; }
      .messages-picker nav :global(button) { width: auto; flex: 0 0 auto; }
      .picker-actions { display: flex; gap: 8px; flex-shrink: 0; min-width: 0; max-width: 100%; }
      .picker-selection { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .sdk__explorer__footer { gap: 12px; }
      .messages-picker :global(.explorer) { width: 100%; min-height: 0; }
      .messages-picker :global(.explorer__container) { width: 100%; }
      .messages-picker > p { padding: 0 24px; margin: 8px 0 12px; font-size: 13px; flex-shrink: 0; }
      @media (max-width: 600px) {
        .messages-picker[data-mobile-ready="true"] > nav,
      .messages-picker[data-mobile-ready="true"] > .sdk__explorer,
      .messages-picker[data-mobile-ready="true"] > .sdk__explorer__footer { display: none; }
      .mobile-share { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 12px; padding: 8px 24px; flex-shrink: 0; }
      .mobile-share p { margin: 4px 0 8px; overflow-wrap: anywhere; }
      .messages-picker nav { padding: 8px 12px; }
        .sdk__explorer__footer { padding: 8px 12px; flex-wrap: wrap; height: auto; }
        .picker-selection { width: 100%; order: -1; }
        .picker-actions { flex-wrap: wrap; width: 100%; }
      }
    `}</style>
  </div>;
}

SuiteFilePicker.getLayout = (page: React.ReactElement) => getSdkLayout(<ColumnPreferencesProvider>{page}</ColumnPreferencesProvider>, true);
