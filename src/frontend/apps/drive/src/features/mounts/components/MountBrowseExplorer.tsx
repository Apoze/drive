import React, { useCallback } from "react";
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
import { MountRenameModal } from "@/features/mounts/components/MountRenameModal";
import { useMountActionController } from "@/features/mounts/components/useMountActionController";
import {
  entryToMountExplorerItem,
  getMountTitle,
  type MountExplorerItem,
} from "@/features/mounts/utils/mountExplorerItems";
import { getMountShellActionIds } from "@/features/mounts/utils/mountShellActions";
import { useMountUploadController } from "@/features/mounts/components/useMountUploadController";

const DEFAULT_LIMIT = 50;

const buildBrowseRoute = (mountId: string, path: string) => ({
  pathname: "/explorer/mounts/[mount_id]",
  query: { mount_id: mountId, path },
});

export const MountBrowseExplorer = () => {
  const { t } = useTranslation();
  const router = useRouter();
  const mountId = String(router.query.mount_id ?? "");
  const normalizedPath =
    typeof router.query.path === "string" && router.query.path
      ? router.query.path
      : "/";

  const createFolderModal = useModal();
  const moveModal = useModal();
  const renameModal = useModal();
  const deleteModal = useModal();
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
  const mapMountBrowsePageItems = useCallback(
    (page: NonNullable<typeof browseQuery.data>["pages"][number]) => {
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
    mountId,
    mountTitle,
    provider: currentMount?.provider,
    normalizedPath,
    onBrowseRefetch: () => browseQuery.refetch(),
  });

  const shellActionIds = getMountShellActionIds(browse);
  const canUploadCurrentFolder = shellActionIds.includes("import_files");
  const canImportFoldersCurrentFolder = shellActionIds.includes("import_folders");
  const canCreateFolderCurrentFolder = shellActionIds.includes("create_folder");
  const {
    uploadLoading,
    mountDropZone,
    mountImportInputs,
    importMenuItems,
  } = useMountUploadController({
    mountId,
    browse,
    canUploadCurrentFolder,
    canImportFoldersCurrentFolder,
    onBrowseRefetch: () => browseQuery.refetch(),
  });
  const shellMenuItems: MenuItem[] = [];

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
      getContextMenuItems={(item) =>
        actionController.getContextMenuItems(item as MountExplorerItem)
      }
      gridHeader={
        <MountExplorerBreadcrumbs
          mountTitle={mountTitle}
          normalizedPath={browse?.normalized_path ?? normalizedPath}
          onNavigateToPath={(path) => {
            void router.push(buildBrowseRoute(mountId, path));
          }}
          actions={
            canUploadCurrentFolder || canCreateFolderCurrentFolder ? (
              <>
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
                    icon={<img src={createFolderSvg.src} alt="Create Folder" />}
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
      }
      onNavigate={(event) => {
        actionController.handleNavigate(event);
      }}
      onFileClick={(item) => actionController.handleFileClick(item as MountExplorerItem)}
      renderAfterExplorer={(childItems) => (
        <>
          <MountFilesPreview
            currentItem={actionController.previewItem}
            items={childItems}
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
          {actionController.activeActionItem && renameModal.isOpen && (
            <MountRenameModal
              isOpen={renameModal.isOpen}
              onClose={() => {
                renameModal.close();
                actionController.clearActionItems();
              }}
              item={actionController.activeActionItem}
              onSuccess={actionController.handleRenameSuccess}
            />
          )}
          {actionController.actionItems.length > 0 && moveModal.isOpen && (
            <MountMoveModal
              isOpen={moveModal.isOpen}
              onClose={() => {
                moveModal.close();
                actionController.clearActionItems();
              }}
              items={actionController.actionItems}
              initialDestinationPath={normalizedPath}
              onSuccess={actionController.handleMoveSuccess}
            />
          )}
          {actionController.actionItems.length > 0 && deleteModal.isOpen && (
            <MountDeleteModal
              isOpen={deleteModal.isOpen}
              onClose={() => {
                deleteModal.close();
                actionController.clearActionItems();
              }}
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
