import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/router";
import { useTranslation } from "react-i18next";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { DropdownMenu, MenuItem } from "@gouvfr-lasuite/ui-kit";
import { AppExplorer } from "@/features/explorer/components/app-view/AppExplorer";
import {
  NavigationEventType,
  useGlobalExplorer,
} from "@/features/explorer/components/GlobalExplorerContext";
import type { EmbeddedExplorerGridActionsCellProps } from "@/features/explorer/components/embedded-explorer/EmbeddedExplorerGridActionsCell";
import { getDriver } from "@/features/config/Config";
import { getGlobalExplorerLayout } from "@/features/layouts/components/explorer/ExplorerLayout";
import {
  MountExplorerBreadcrumbs,
  MountExplorerPrimaryAction,
} from "@/features/mounts/components/MountExplorerBreadcrumbs";
import { MountFilesPreview } from "@/features/mounts/components/MountFilesPreview";
import {
  entryToMountExplorerItem,
  getMountExplorerMeta,
  getMountTitle,
  type MountExplorerItem,
} from "@/features/mounts/utils/mountExplorerItems";
import { errorToString } from "@/features/api/APIError";
import { addToast, ToasterItem } from "@/features/ui/components/toaster/Toaster";

const DEFAULT_LIMIT = 50;

const buildBrowseRoute = (mountId: string, path: string) => ({
  pathname: "/explorer/mounts/[mount_id]",
  query: { mount_id: mountId, path },
});

const buildWopiRoute = (mountId: string, path: string) => ({
  pathname: "/explorer/mounts/[mount_id]/wopi",
  query: { mount_id: mountId, path },
});

const MountSelectionBarActions = ({
  onBrowse,
  onPreview,
  onDownload,
  onWopi,
  onShare,
}: {
  onBrowse: (item: MountExplorerItem) => void;
  onPreview: (item: MountExplorerItem) => void;
  onDownload: (item: MountExplorerItem) => void;
  onWopi: (item: MountExplorerItem) => void;
  onShare: (item: MountExplorerItem) => void;
}) => {
  const { t } = useTranslation();
  const { selectedItems } = useGlobalExplorer();

  if (selectedItems.length !== 1) {
    return null;
  }

  const item = selectedItems[0] as MountExplorerItem;
  const meta = getMountExplorerMeta(item);

  if (meta.entryType === "folder") {
    return (
      <>
        <Button variant="tertiary" size="small" onClick={() => onBrowse(item)}>
          {t("explorer.mounts.browse")}
        </Button>
        {meta.abilities?.share_link_create && (
          <Button variant="tertiary" size="small" onClick={() => onShare(item)}>
            {t("explorer.mounts.actions.share")}
          </Button>
        )}
      </>
    );
  }

  return (
    <>
      {meta.abilities?.preview && (
        <Button variant="tertiary" size="small" onClick={() => onPreview(item)}>
          {t("explorer.mounts.actions.preview")}
        </Button>
      )}
      <Button variant="tertiary" size="small" onClick={() => onDownload(item)}>
        {t("explorer.mounts.actions.download")}
      </Button>
      {meta.abilities?.wopi && (
        <Button variant="tertiary" size="small" onClick={() => onWopi(item)}>
          {t("explorer.mounts.actions.wopi")}
        </Button>
      )}
      {meta.abilities?.share_link_create && (
        <Button variant="tertiary" size="small" onClick={() => onShare(item)}>
          {t("explorer.mounts.actions.share")}
        </Button>
      )}
    </>
  );
};

const MountGridActionsCell = ({
  params,
  getMenuItems,
}: {
  params: EmbeddedExplorerGridActionsCellProps;
  getMenuItems: (item: MountExplorerItem) => MenuItem[];
}) => {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const item = params.row.original as MountExplorerItem;

  return (
    <div
      onClick={(event) => {
        event.stopPropagation();
      }}
    >
      <DropdownMenu options={getMenuItems(item)} isOpen={isOpen} onOpenChange={setIsOpen}>
        <Button
          variant="tertiary"
          size="nano"
          aria-label={t("explorer.grid.actions.button_aria_label", {
            name: item.title,
          })}
          icon={<span className="material-icons">more_horiz</span>}
          onClick={() => setIsOpen(!isOpen)}
        />
      </DropdownMenu>
    </div>
  );
};

export default function MountBrowsePage() {
  const { t } = useTranslation();
  const router = useRouter();
  const mountId = String(router.query.mount_id ?? "");
  const normalizedPath =
    typeof router.query.path === "string" && router.query.path
      ? router.query.path
      : "/";

  const [uploadLoading, setUploadLoading] = useState(false);
  const [previewItem, setPreviewItem] = useState<MountExplorerItem>();
  const uploadInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setPreviewItem(undefined);
  }, [mountId, normalizedPath]);

  const { data: mounts } = useQuery({
    queryKey: ["mounts", "discovery"],
    refetchOnWindowFocus: false,
    queryFn: () => getDriver().getMountsDiscovery(),
  });

  const currentMount = mounts?.find((mount) => mount.mount_id === mountId);
  const mountTitle = currentMount ? getMountTitle(currentMount) : "SMB";

  const browseQuery = useInfiniteQuery({
    queryKey: ["mounts", "browse", mountId, normalizedPath, DEFAULT_LIMIT],
    enabled: Boolean(mountId),
    initialPageParam: 0,
    refetchOnWindowFocus: false,
    queryFn: ({ pageParam }) =>
      getDriver().browseMount({
        mountId,
        path: normalizedPath,
        limit: DEFAULT_LIMIT,
        offset: Number(pageParam),
      }),
    getNextPageParam: (lastPage, allPages) => {
      const count = lastPage.children?.count ?? 0;
      const loaded = allPages.reduce(
        (total, page) => total + (page.children?.results.length ?? 0),
        0,
      );
      return loaded < count ? loaded : undefined;
    },
  });

  const browse = browseQuery.data?.pages[0];

  const childItems = useMemo(() => {
    if (!browseQuery.data) {
      return [];
    }
    return browseQuery.data.pages.flatMap((page) =>
      (page.children?.results ?? []).map((entry) =>
        entryToMountExplorerItem(
          mountId,
          entry,
          mountTitle,
          currentMount?.provider,
        ),
      ),
    );
  }, [browseQuery.data, currentMount?.provider, mountId, mountTitle]);

  const navigateToPath = (path: string) => {
    void router.push(buildBrowseRoute(mountId, path));
  };

  const handleBrowseItem = (item: MountExplorerItem) => {
    const meta = getMountExplorerMeta(item);
    navigateToPath(meta.normalizedPath);
  };

  const handlePreviewItem = (item: MountExplorerItem) => {
    if (!getMountExplorerMeta(item).abilities?.preview) {
      return;
    }
    setPreviewItem(item);
  };

  const handleDownloadItem = (item: MountExplorerItem) => {
    if (!item.url) {
      return;
    }
    window.open(item.url, "_blank", "noreferrer");
  };

  const handleWopiItem = (item: MountExplorerItem) => {
    const meta = getMountExplorerMeta(item);
    void router.push(buildWopiRoute(meta.mountId, meta.normalizedPath));
  };

  const handleShareItem = async (item: MountExplorerItem) => {
    const meta = getMountExplorerMeta(item);
    try {
      const response = await getDriver().createMountShareLink({
        mountId: meta.mountId,
        path: meta.normalizedPath,
      });
      try {
        await navigator.clipboard.writeText(response.share_url);
      } catch {
        // Clipboard failures are non-blocking; the URL is still shown in the toast.
      }
      addToast(
        <ToasterItem>
          <span>{response.share_url}</span>
        </ToasterItem>,
      );
    } catch (error) {
      addToast(
        <ToasterItem type="error">{errorToString(error)}</ToasterItem>,
      );
    }
  };

  const getMenuItems = (item: MountExplorerItem): MenuItem[] => {
    const meta = getMountExplorerMeta(item);

    if (meta.entryType === "folder") {
      return [
        {
          icon: <span className="material-icons">folder_open</span>,
          label: t("explorer.mounts.browse"),
          callback: () => handleBrowseItem(item),
        },
        {
          icon: <span className="material-icons">share</span>,
          label: t("explorer.mounts.actions.share"),
          isHidden: !meta.abilities?.share_link_create,
          callback: () => void handleShareItem(item),
        },
      ];
    }

    return [
      {
        icon: <span className="material-icons">visibility</span>,
        label: t("explorer.mounts.actions.preview"),
        isHidden: !meta.abilities?.preview,
        callback: () => handlePreviewItem(item),
      },
      {
        icon: <span className="material-icons">download</span>,
        label: t("explorer.mounts.actions.download"),
        isHidden: !item.url,
        callback: () => handleDownloadItem(item),
      },
      {
        icon: <span className="material-icons">edit</span>,
        label: t("explorer.mounts.actions.wopi"),
        isHidden: !meta.abilities?.wopi,
        callback: () => handleWopiItem(item),
      },
      {
        icon: <span className="material-icons">share</span>,
        label: t("explorer.mounts.actions.share"),
        isHidden: !meta.abilities?.share_link_create,
        callback: () => void handleShareItem(item),
      },
    ];
  };

  const handleUpload = async (file: File) => {
    if (!browse || browse.entry.entry_type !== "folder") {
      return;
    }
    setUploadLoading(true);
    try {
      await getDriver().uploadMountFile({
        mountId,
        path: browse.normalized_path,
        file,
      });
      addToast(<ToasterItem>{t("explorer.mounts.upload.success")}</ToasterItem>);
      await browseQuery.refetch();
    } catch (error) {
      addToast(
        <ToasterItem type="error">{errorToString(error)}</ToasterItem>,
      );
    } finally {
      setUploadLoading(false);
      if (uploadInputRef.current) {
        uploadInputRef.current.value = "";
      }
    }
  };

  if (browseQuery.isLoading) {
    return <div>{t("explorer.mounts.browse_loading")}</div>;
  }

  if (browseQuery.isError || !browse) {
    return (
      <div>
        <div>{t("explorer.mounts.browse_error")}</div>
        <Button variant="tertiary" onClick={() => browseQuery.refetch()}>
          {t("common.retry")}
        </Button>
      </div>
    );
  }

  const canUploadCurrentFolder =
    browse.entry.entry_type === "folder" &&
    Boolean(browse.capabilities["mount.upload"]) &&
    browse.entry.abilities.upload;

  return (
    <>
      <input
        ref={uploadInputRef}
        type="file"
        style={{ display: "none" }}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) {
            void handleUpload(file);
          }
        }}
      />
      <AppExplorer
        childrenItems={childItems}
        showFilters={false}
        preserveIdleTopBarSpace
        disableItemDragAndDrop
        disableDefaultContextMenu
        hasNextPage={browseQuery.hasNextPage}
        isFetchingNextPage={browseQuery.isFetchingNextPage}
        fetchNextPage={() => {
          void browseQuery.fetchNextPage();
        }}
        selectionBarActions={
          <MountSelectionBarActions
            onBrowse={handleBrowseItem}
            onPreview={handlePreviewItem}
            onDownload={handleDownloadItem}
            onWopi={handleWopiItem}
            onShare={(item) => {
              void handleShareItem(item);
            }}
          />
        }
        gridActionsCell={(params) => (
          <MountGridActionsCell params={params} getMenuItems={getMenuItems} />
        )}
        getContextMenuItems={getMenuItems}
        gridHeader={
          <MountExplorerBreadcrumbs
            mountTitle={mountTitle}
            normalizedPath={browse.normalized_path}
            onNavigateToPath={navigateToPath}
            actions={
              canUploadCurrentFolder ? (
                <MountExplorerPrimaryAction
                  label={t("explorer.mounts.actions.upload")}
                  onClick={() => uploadInputRef.current?.click()}
                  disabled={uploadLoading}
                />
              ) : undefined
            }
          />
        }
        onNavigate={(event) => {
          if (event.type !== NavigationEventType.ITEM) {
            return;
          }
          handleBrowseItem(event.item as MountExplorerItem);
        }}
        onFileClick={handlePreviewItem}
      />
      <MountFilesPreview
        currentItem={previewItem}
        items={childItems}
        setPreviewItem={setPreviewItem}
      />
    </>
  );
}

MountBrowsePage.getLayout = getGlobalExplorerLayout;
