import { ExplorerCreateFileModal } from "@/features/explorer/components/modals/ExplorerCreateFileModal";
import { useConfig } from "@/features/config/ConfigProvider";
import { openFileFromExplorer } from "@/features/explorer/utils/fileOpenAction";
import { docsCreationUrl } from "@/features/explorer/utils/docsNavigation";
import React, { useCallback, useState } from "react";
import { useRouter } from "next/router";
import { useTranslation } from "react-i18next";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Button, useModal } from "@gouvfr-lasuite/cunningham-react";
import {
  ContextMenu,
  DropdownMenu,
  MenuItem,
  useDropdownMenu,
} from "@gouvfr-lasuite/ui-kit";
import createFolderSvg from "@/assets/icons/add_folder.svg";
import { BrowseExplorerTemplate } from "@/features/explorer/components/shared-browse/BrowseExplorerTemplate";
import { getDriver } from "@/features/config/Config";
import { MountExplorerBreadcrumbs } from "@/features/mounts/components/MountExplorerBreadcrumbs";
import { MountCreateFolderModal } from "@/features/mounts/components/MountCreateFolderModal";
import { MountDeleteModal } from "@/features/mounts/components/MountDeleteModal";
import { MountFilesPreview } from "@/features/mounts/components/MountFilesPreview";
import { MountMoveModal } from "@/features/mounts/components/MountMoveModal";
import { StorageTransferModal } from "@/features/storage/StorageTransferModal";
import { MountRenameModal } from "@/features/mounts/components/MountRenameModal";
import { useMountActionController } from "@/features/mounts/components/useMountActionController";
import {
  entryToMountExplorerItem,
  getMountTitle,
  type MountExplorerItem,
} from "@/features/mounts/utils/mountExplorerItems";
import { getMountShellActionIds } from "@/features/mounts/utils/mountShellActions";
import { useMountUploadController } from "@/features/mounts/components/useMountUploadController";
import {
  StorageResource,
  resourceItem,
  resourceHref,
  StoragePage,
  storageRequest,
} from "@/features/storage/api";
import { Item, ItemType, MountBrowseResponse } from "@/features/drivers/types";
import { useItemActionMenuItems } from "@/features/explorer/hooks/useItemActionMenuItems";

const DEFAULT_LIMIT = 50;
type BrowsePage = MountBrowseResponse & { resources?: StorageResource[] };

const buildBrowseRoute = (mountId: string, path: string) => ({
  pathname: "/explorer/mounts/[mount_id]",
  query: { mount_id: mountId, path },
});

export const MountBrowseExplorer = (
  props: {
    mountId?: string;
    path?: string;
    onNavigateToPath?: (path: string) => void;
    resource?: StorageResource;
    unified?: boolean;
  } = {},
) => {
  const { t, i18n } = useTranslation();
  const { config } = useConfig();
  const documentActions = useItemActionMenuItems();
  const [documentOpenFailed, setDocumentOpenFailed] = useState(false);
  const router = useRouter();
  const mountId = props.mountId ?? String(router.query.mount_id ?? "");
  const normalizedPath =
    props.path ??
    (typeof router.query.path === "string" && router.query.path
      ? router.query.path
      : "/");

  const createFolderModal = useModal();
  const importDropdown = useDropdownMenu();

  const { data: mounts } = useQuery({
    queryKey: ["mounts", "discovery"],
    refetchOnWindowFocus: false,
    queryFn: () => getDriver().getMountsDiscovery(),
  });

  const currentMount = mounts?.find((mount) => mount.mount_id === mountId);
  const mountTitle = currentMount
    ? getMountTitle(currentMount)
    : mountId || "Mount";

  const browseQuery = useInfiniteQuery({
    queryKey: [
      "mounts",
      "browse",
      mountId,
      normalizedPath,
      DEFAULT_LIMIT,
      props.resource?.id,
    ],
    enabled: Boolean(mountId),
    initialPageParam: 0,
    refetchOnWindowFocus: false,
    queryFn: async ({ pageParam }): Promise<BrowsePage> => {
      if (props.resource?.adapter.kind === "mount") {
        const page = await storageRequest<StoragePage<StorageResource>>(
          `resources/${props.resource.id}/children/`,
          {
            params: {
              space: props.resource.space,
              offset: Number(pageParam),
              limit: DEFAULT_LIMIT,
            },
          },
        );
        const adapter = props.resource.adapter;
        return {
          resources: page.results,
          mount_id: mountId,
          normalized_path: adapter.path,
          entry: adapter.entry,
          capabilities: adapter.capabilities,
          children: {
            count: page.count,
            next: page.next,
            results: page.results.flatMap((row) =>
              row.adapter.kind === "mount" ? [row.adapter.entry] : [],
            ),
          },
        };
      }
      return getDriver().browseMount({
        mountId,
        path: normalizedPath,
        limit: DEFAULT_LIMIT,
        offset: Number(pageParam),
      });
    },
    getNextPageParam: (lastPage, allPages) => {
      const count = lastPage.children?.count ?? 0;
      const loaded = allPages.reduce(
        (total, page) =>
          total +
          (page.resources?.length ?? page.children?.results.length ?? 0),
        0,
      );
      return loaded < count ? loaded : undefined;
    },
  });

  const browse = browseQuery.data?.pages[0];
  const mapMountBrowsePageItems = useCallback(
    (page: NonNullable<typeof browseQuery.data>["pages"][number]): Item[] => {
      if (page.resources) return page.resources.map(resourceItem);
      return (page.children?.results ?? []).map((entry) =>
        entryToMountExplorerItem(
          mountId,
          entry,
          mountTitle,
          currentMount?.provider,
        ),
      );
    },
    [currentMount?.provider, mountId, mountTitle],
  );

  const handleCreateFolderSuccess = (
    entry: Parameters<typeof entryToMountExplorerItem>[1],
  ) => {
    const createdItem = entryToMountExplorerItem(
      mountId,
      entry,
      mountTitle,
      currentMount?.provider,
    );
    actionController.handleCreateFolderSelection(createdItem);
    void browseQuery.refetch();
  };
  const actionController = useMountActionController({
    unified: props.unified || Boolean(props.resource),
    mountId,
    mountTitle,
    provider: currentMount?.provider,
    normalizedPath,
    onNavigateToPath: props.onNavigateToPath,
    onBrowseRefetch: () => browseQuery.refetch(),
  });

  const shellActionIds = getMountShellActionIds(browse);
  const canUploadCurrentFolder = shellActionIds.includes("import_files");
  const canImportFoldersCurrentFolder =
    shellActionIds.includes("import_folders");
  const canCreateFolderCurrentFolder = shellActionIds.includes("create_folder");
  const { uploadLoading, mountDropZone, mountImportInputs, importMenuItems } =
    useMountUploadController({
      mountId,
      browse,
      canUploadCurrentFolder,
      canImportFoldersCurrentFolder,
      onBrowseRefetch: () => browseQuery.refetch(),
    });
  const createFileModal = useModal();
  const canCreateFile = canUploadCurrentFolder && Boolean(props.resource);
  const docsUrl =
    config.DOCS_DRIVE_ENABLED &&
    canCreateFile &&
    docsCreationUrl(
      config.DOCS_PUBLIC_URL,
      props.resource?.id,
      props.resource?.space,
    );
  const openDocsCreation = () => {
    if (docsUrl) window.open(docsUrl, "_blank", "noopener,noreferrer");
  };
  const shellMenuItems: MenuItem[] = [];
  if (docsUrl)
    shellMenuItems.push({
      label: t("explorer.actions.createDocs"),
      callback: openDocsCreation,
    });
  if (canCreateFile)
    shellMenuItems.push({
      label: t("explorer.actions.createFile.modal.title"),
      callback: createFileModal.open,
    });

  if (canCreateFolderCurrentFolder) {
    shellMenuItems.push({
      icon: <span className="material-icons">create_new_folder</span>,
      label: t("explorer.actions.createFolder.modal.title"),
      callback: createFolderModal.open,
    });
  }

  if (canCreateFolderCurrentFolder && importMenuItems.length > 0) {
    shellMenuItems.push({ type: "separator" });
  }

  shellMenuItems.push(...importMenuItems);

  const openDocument = (item: Item) => {
    setDocumentOpenFailed(false);
    openFileFromExplorer({
      item,
      openPreview: () => undefined,
      onPreviewUnavailable: () => setDocumentOpenFailed(true),
    });
  };
  const explorer = (
    <BrowseExplorerTemplate
      data={browseQuery.data}
      viewConfigKey="folder"
      mapPageItems={mapMountBrowsePageItems}
      isLoading={browseQuery.isLoading}
      isError={browseQuery.isError || !browse}
      loadingLabel={t("explorer.mounts.browse_loading")}
      errorLabel={t("explorer.mounts.browse_error")}
      onRetry={() => {
        void browseQuery.refetch();
      }}
      dropZone={mountDropZone}
      showFilters={false}
      preserveIdleTopBarSpace
      disableDefaultContextMenu
      hasNextPage={browseQuery.hasNextPage}
      isFetchingNextPage={browseQuery.isFetchingNextPage}
      fetchNextPage={() => {
        void browseQuery.fetchNextPage();
      }}
      selectionBarActions={actionController.selectionBarActions}
      canSelect={(item) => item.abilities.retrieve}
      getContextMenuItems={(item) =>
        item.type === ItemType.DOCS
          ? [
              {
                label: `${t("storage.open")} Docs`,
                isHidden: !item.abilities.open_docs,
                callback: () => openDocument(item),
              },
              {
                label: t("explorer.mounts.browse"),
                isHidden: !item.abilities.children_list,
                callback: () => {
                  void router.push(
                    resourceHref(item.id, props.resource?.space),
                  );
                },
              },
              ...documentActions.getMenuItems(item),
            ]
          : actionController.getContextMenuItems(item as MountExplorerItem)
      }
      gridHeader={
        <>
          {documentOpenFailed && <p role="alert">{t("storage.load_error")}</p>}
          <MountExplorerBreadcrumbs
            unified={props.unified || Boolean(props.resource)}
            mountTitle={mountTitle}
            normalizedPath={browse?.normalized_path ?? normalizedPath}
            onNavigateToPath={(path) => {
              if (props.onNavigateToPath) props.onNavigateToPath(path);
              else void router.push(buildBrowseRoute(mountId, path));
            }}
            actions={
              canUploadCurrentFolder || canCreateFolderCurrentFolder ? (
                <>
                  {docsUrl && (
                    <Button
                      variant="tertiary"
                      size="small"
                      onClick={openDocsCreation}
                    >
                      {t("explorer.actions.createDocs")}
                    </Button>
                  )}
                  {canCreateFile && (
                    <Button
                      variant="tertiary"
                      size="small"
                      onClick={createFileModal.open}
                    >
                      {t("explorer.actions.createFile.modal.title")}
                    </Button>
                  )}
                  {canUploadCurrentFolder && (
                    <DropdownMenu
                      options={importMenuItems}
                      {...importDropdown}
                      onOpenChange={importDropdown.setIsOpen}
                    >
                      <Button
                        variant="tertiary"
                        size="small"
                        onClick={() => {
                          importDropdown.setIsOpen(true);
                        }}
                        disabled={uploadLoading}
                      >
                        {t("explorer.tree.import.label")}
                      </Button>
                    </DropdownMenu>
                  )}
                  {canCreateFolderCurrentFolder && (
                    <Button
                      icon={
                        <img src={createFolderSvg.src} alt="Create Folder" />
                      }
                      variant="tertiary"
                      data-testid="mount-create-folder-button"
                      size="small"
                      onClick={createFolderModal.open}
                    />
                  )}
                </>
              ) : undefined
            }
          />
          {currentMount?.storage_status && (
            <p role="status">
              {currentMount.storage_status.maintenance
                ? t("explorer.mounts.storage_maintenance")
                : currentMount.storage_status.inventory_updated_at
                  ? t("explorer.mounts.storage_synchronized", {
                      date: new Date(
                        currentMount.storage_status.inventory_updated_at,
                      ).toLocaleString(i18n.language),
                    })
                  : t("explorer.mounts.storage_initializing")}
            </p>
          )}
        </>
      }
      onNavigate={(event) => {
        if (
          "item" in event &&
          "type" in event.item &&
          event.item.type === ItemType.DOCS
        ) {
          openDocument({ ...event.item, children: undefined });
        } else actionController.handleNavigate(event);
      }}
      onFileClick={(item) =>
        item.type === ItemType.DOCS
          ? openDocument(item)
          : actionController.handleFileClick(item as MountExplorerItem)
      }
      renderAfterExplorer={(childItems) => (
        <>
          {documentActions.modals}
          {actionController.copyModal}
          {createFileModal.isOpen && props.resource && (
            <ExplorerCreateFileModal
              {...createFileModal}
              nativeFolder={{
                id: props.resource.id,
                space: props.resource.space,
              }}
              canCreateChildren
              onCreated={(created) => {
                void browseQuery.refetch();
                if ("mountMeta" in created)
                  actionController.handleFileClick(
                    created as MountExplorerItem,
                  );
              }}
            />
          )}
          <MountFilesPreview
            currentItem={actionController.previewItem}
            items={childItems.filter(
              (item): item is MountExplorerItem => "mountMeta" in item,
            )}
            setPreviewCurrentItem={actionController.setPreviewCurrentItem}
          />
          {createFolderModal.isOpen && browse && (
            <MountCreateFolderModal
              isOpen={createFolderModal.isOpen}
              onClose={createFolderModal.close}
              mountId={mountId}
              parentPath={browse.normalized_path}
              onSuccess={handleCreateFolderSuccess}
            />
          )}
          {actionController.activeActionItem &&
            actionController.action === "rename" && (
              <MountRenameModal
                isOpen
                onClose={actionController.clearActionItems}
                item={actionController.activeActionItem}
                onSuccess={actionController.handleRenameSuccess}
              />
            )}
          {actionController.actionItems.length > 0 &&
            actionController.action === "move" &&
            (props.unified || props.resource ? (
              <StorageTransferModal
                mode="move"
                items={actionController.actionItems}
                onClose={actionController.clearActionItems}
              />
            ) : (
              <MountMoveModal
                isOpen
                onClose={actionController.clearActionItems}
                items={actionController.actionItems}
                initialDestinationPath={normalizedPath}
                onSuccess={actionController.handleMoveSuccess}
              />
            ))}
          {actionController.actionItems.length > 0 &&
            actionController.action === "delete" && (
              <MountDeleteModal
                isOpen
                onClose={actionController.clearActionItems}
                items={actionController.actionItems}
                onSuccess={actionController.handleDeleteSuccess}
              />
            )}
        </>
      )}
    />
  );

  return (
    <>
      {mountImportInputs}
      {shellMenuItems.length > 0 ? (
        <ContextMenu options={shellMenuItems}>{explorer}</ContextMenu>
      ) : (
        explorer
      )}
    </>
  );
};
