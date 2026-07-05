import React from "react";
import {
  type CSSProperties,
  SetStateAction,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Dispatch } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Item,
  ItemBreadcrumb,
  ItemType,
  TreeItem,
} from "@/features/drivers/types";
import { createContext } from "react";
import { getDriver } from "@/features/config/Config";
import { Toaster } from "@/features/ui/components/toaster/Toaster";
import { useDropzone } from "react-dropzone";
import { useUploadZone } from "../hooks/useUpload";

import {
  TreeProvider,
  TreeViewDataType,
  TreeViewNodeTypeEnum,
  useTreeContext,
} from "@gouvfr-lasuite/ui-kit";
import { ExplorerDndProvider } from "./ExplorerDndProvider";
import { useFirstLevelItems } from "../hooks/useQueries";
import { useTranslation } from "react-i18next";
import { SpinnerPage } from "@/features/ui/components/spinner/SpinnerPage";

import { useAuth } from "@/features/auth/Auth";
import { DefaultRoute } from "@/utils/defaultRoutes";
import {
  buildMountsTreeRoot,
  discoveryToMountTreeItem,
  entryToMountTreeItem,
  getMountTreeNodeId,
  isMountsTreeRootId,
  parseMountTreeNodeId,
} from "@/features/mounts/utils/mountTree";
import { getMountTitle } from "@/features/mounts/utils/mountExplorerItems";
import { getParentMountPath } from "@/features/mounts/utils/mountBulkActions";
import { createItemsPreviewController } from "@/features/explorer/components/items-browse/itemsPreviewController";
import { createRightPanelController } from "@/features/explorer/components/right-panel/rightPanelController";
import { createSelectionController } from "@/features/explorer/components/selection/selectionController";
import {
  ITEM_IMPORT_FILES_INPUT_ID,
  ITEM_IMPORT_FOLDERS_INPUT_ID,
} from "@/features/explorer/components/item-actions/itemImportMenuItems";
import {
  getOriginalIdFromTreeId,
  itemToTreeItem,
} from "./explorerTreeData";

export interface GlobalExplorerContextType {
  displayMode: "sdk" | "app";
  selectedItems: Item[];
  selectedItemsMap: Record<string, Item>;
  mainWorkspace: Item | undefined;
  setSelectedItems: Dispatch<SetStateAction<Item[]>>;
  clearSelection: () => void;
  replaceSelection: (items: Item[]) => void;
  selectSingleItem: (item: Item) => void;
  itemId: string;
  item: Item | undefined;
  firstLevelItems: Item[] | undefined;
  onNavigate: (event: NavigationEvent) => void;
  initialId: string | undefined;
  treeIsInitialized: boolean;
  setTreeIsInitialized: (isInitialized: boolean) => void;
  dropZone: ReturnType<typeof useDropzone>;
  rightPanelForcedItem?: Item;
  setRightPanelForcedItem: (item: Item | undefined) => void;
  rightPanelOpen: boolean;
  setRightPanelOpen: (open: boolean) => void;
  openRightPanelForItem: (item: Item) => void;
  closeRightPanel: () => void;
  clearRightPanelItem: () => void;
  replaceRightPanelItem: (item: Item | undefined) => void;
  replaceRightPanelItemIfCurrent: (currentItemId: string, nextItem: Item) => void;
  closeRightPanelIfCurrent: (itemId: string) => void;
  closeRightPanelIfIncluded: (items: Array<Pick<Item, "id">> | string[]) => void;
  isLeftPanelOpen: boolean;
  setIsLeftPanelOpen: (isLeftPanelOpen: boolean) => void;
  previewItem?: Item;
  previewItems: Item[];
  setPreviewCurrentItem: (item: Item | undefined) => void;
  replacePreviewItems: (items: Item[]) => void;
  openPreview: (item: Item, items: Item[]) => void;
  openSinglePreview: (item: Item) => void;
  closePreview: () => void;
  isMinimalLayout?: boolean;
  refreshMobileNodes: () => void;
  mobileNodesRefreshTrigger: number;
}

export const GlobalExplorerContext = createContext<
  GlobalExplorerContextType | undefined
>(undefined);

export {
  generateTreeId,
  getOriginalIdFromTreeId,
  itemToTreeItem,
  itemsToTreeItems,
} from "./explorerTreeData";

const DROPZONE_INPUT_HIDDEN_STYLE: CSSProperties = {
  border: 0,
  clip: "rect(0, 0, 0, 0)",
  clipPath: "inset(50%)",
  height: "1px",
  left: 0,
  margin: 0,
  overflow: "hidden",
  padding: 0,
  position: "fixed",
  top: 0,
  whiteSpace: "nowrap",
  width: "1px",
};

export const useGlobalExplorer = () => {
  const context = useContext(GlobalExplorerContext);
  if (!context) {
    throw new Error(
      "useGlobalExplorer must be used within an GlobalExplorerProvider",
    );
  }
  return context;
};

export enum NavigationEventType {
  ITEM,
}

export type NavigationEvent = {
  type: NavigationEventType.ITEM;
  item: NavigationItem;
};

export type NavigationItem = Item | ItemBreadcrumb | TreeItem;

interface ExplorerProviderProps {
  children: React.ReactNode;
  displayMode: "sdk" | "app";
  itemId: string;
  onNavigate: (event: NavigationEvent) => void;
}

/**
 * - Handles the selection of items
 * - Handles the right panel states
 * - Handles the left panel states
 * - Sets TreeProvider
 * - Sets ExplorerDndProvider
 * - Sets Toaster
 *
 * Behavior:
 *
 * We first try to request the current item if it exists, if so, we enable the
 * next queries ( /tree and /items ). We don't start all the queries at once just
 * to make sure the item is accessible. If the item is not accessible, the backend
 * returns 401 or 403 errors and the we let the handler redirect to the 401 or 403 page.
 */
export const GlobalExplorerProvider = ({
  children,
  displayMode = "app",
  itemId,
  onNavigate,
}: ExplorerProviderProps) => {
  const driver = getDriver();
  const { user } = useAuth();
  const { t } = useTranslation();
  const mountDiscoveriesCache = useRef<Record<string, Awaited<ReturnType<typeof driver.getMountsDiscovery>>[number]>>({});

  const [selectedItems, setSelectedItems] = useState<Item[]>([]);
  const selectionController = useMemo(
    () =>
      createSelectionController<Item>({
        setSelectedItems,
      }),
    [],
  );

  // Avoid inifinite rerendering
  const selectedItemsMap = useMemo(() => {
    const map: Record<string, Item> = {};
    selectedItems.forEach((item) => {
      map[item.id] = item;
    });
    return map;
  }, [selectedItems]);

  const [rightPanelForcedItem, setRightPanelForcedItem] = useState<Item>();
  const [rightPanelOpen, setRightPanelOpen] = useState(false);
  const rightPanelController = useMemo(
    () =>
      createRightPanelController({
        rightPanelForcedItem,
        setRightPanelForcedItem,
        rightPanelOpen,
        setRightPanelOpen,
      }),
    [rightPanelForcedItem, rightPanelOpen],
  );
  const [isLeftPanelOpen, setIsLeftPanelOpen] = useState(false);

  const [initialId] = useState<string | undefined>(itemId);
  const [isInitialized, setIsInitialized] = useState<boolean>(false);
  const [treeIsInitialized, setTreeIsInitialized] = useState<boolean>(false);
  const [mobileNodesRefreshTrigger, setMobileNodesRefreshTrigger] = useState(0);

  /**
   * Triggers a refresh of the mobile nodes.
   * We do this as a hack because we can't act the same as we do with the desktop tree because the tree is imperative not reactive.
   */
  const refreshMobileNodes = () => {
    setMobileNodesRefreshTrigger((prev) => prev + 1);
  };

  const { data: item } = useQuery({
    queryKey: ["items", itemId],
    queryFn: () => getDriver().getItem(itemId),
    enabled: !!itemId,
  });

  useEffect(() => {
    if (isInitialized) {
      return;
    }
    if (!initialId) {
      setIsInitialized(true);
      return;
    }
    if (item) {
      setIsInitialized(true);
    }
  }, [initialId, isInitialized, item]);

  const { data: firstLevelItems } = useFirstLevelItems();

  const mainWorkspace = useMemo(() => {
    if (user && user.main_workspace) {
      return user.main_workspace;
    }

    return firstLevelItems?.find((item) => item.main_workspace);
  }, [firstLevelItems, user]);

  useEffect(() => {
    // If we open the right panel and we have a selection, we need to clear it.
    if (rightPanelForcedItem?.id === itemId) {
      selectionController.clearSelection();
    }
  }, [itemId, rightPanelForcedItem, selectionController]);

  /**
   * We need to force the current folder to be displayed in the right panel.
   */
  useEffect(() => {
    if (rightPanelOpen) {
      selectionController.clearSelection();
    }
  }, [rightPanelOpen, selectionController]);

  const { dropZone } = useUploadZone({ item: item! });

  /**
   * Preview states.
   */
  const [previewItem, setPreviewItem] = useState<Item | undefined>(undefined);
  const [previewItems, setPreviewItems] = useState<Item[]>([]);
  const itemsPreviewController = useMemo(
    () =>
      createItemsPreviewController({
        setPreviewCurrentItem: setPreviewItem,
        replacePreviewItems: setPreviewItems,
      }),
    [],
  );

  const loadMountDiscoveries = async () => {
    if (Object.keys(mountDiscoveriesCache.current).length > 0) {
      return Object.values(mountDiscoveriesCache.current);
    }

    const mounts = await driver.getMountsDiscovery();
    mountDiscoveriesCache.current = Object.fromEntries(
      mounts.map((mount) => [mount.mount_id, mount]),
    );
    return mounts;
  };

  const loadMountFolderChildren = async ({
    mountId,
    normalizedPath,
    parentId,
  }: {
    mountId: string;
    normalizedPath: string;
    parentId: string;
  }) => {
    const mounts = await loadMountDiscoveries();
    const currentMount = mounts.find((mount) => mount.mount_id === mountId);
    const mountTitle = currentMount ? getMountTitle(currentMount) : mountId;
    const provider = currentMount?.provider;

    const children: TreeItem[] = [];
    const limit = 200;
    let offset = 0;

    while (true) {
      const browse = await driver.browseMount({
        mountId,
        path: normalizedPath,
        limit,
        offset,
      });

      const folderChildren =
        browse.children?.results.filter((entry) => entry.entry_type === "folder") ?? [];

      children.push(
        ...folderChildren.map((entry) =>
          entryToMountTreeItem({
            mountId,
            entry,
            mountTitle,
            provider,
            parentId,
          }),
        ),
      );

      if (!browse.children?.next) {
        break;
      }

      offset += limit;
    }

    return {
      children,
      pagination: {
        currentPage: 1,
        totalCount: children.length,
        hasMore: false,
      },
    };
  };


  return (
    <GlobalExplorerContext.Provider
      value={{
        treeIsInitialized,
        setTreeIsInitialized,
        firstLevelItems,
        displayMode,
        selectedItems,
        selectedItemsMap,
        mainWorkspace,
        setSelectedItems,
        clearSelection: selectionController.clearSelection,
        replaceSelection: selectionController.replaceSelection,
        selectSingleItem: selectionController.selectSingleItem,
        itemId,
        initialId,
        item,
        onNavigate,
        dropZone,
        rightPanelForcedItem,
        setRightPanelForcedItem,
        rightPanelOpen,
        setRightPanelOpen,
        openRightPanelForItem: rightPanelController.openRightPanelForItem,
        closeRightPanel: rightPanelController.closeRightPanel,
        clearRightPanelItem: rightPanelController.clearRightPanelItem,
        replaceRightPanelItem: rightPanelController.replaceRightPanelItem,
        replaceRightPanelItemIfCurrent:
          rightPanelController.replaceRightPanelItemIfCurrent,
        closeRightPanelIfCurrent:
          rightPanelController.closeRightPanelIfCurrent,
        closeRightPanelIfIncluded:
          rightPanelController.closeRightPanelIfIncluded,
        isLeftPanelOpen,
        setIsLeftPanelOpen,
        previewItem,
        previewItems,
        setPreviewCurrentItem: itemsPreviewController.setPreviewCurrentItem,
        replacePreviewItems: itemsPreviewController.replacePreviewItems,
        openPreview: itemsPreviewController.openPreview,
        openSinglePreview: itemsPreviewController.openSinglePreview,
        closePreview: itemsPreviewController.closePreview,
        refreshMobileNodes,
        mobileNodesRefreshTrigger,
      }}
    >
      <TreeProvider
        initialTreeData={[]}
        initialNodeId={initialId}
        onLoadChildren={async (treeId, page) => {
          if (isMountsTreeRootId(treeId)) {
            const mounts = await loadMountDiscoveries();
            const children = mounts.map((mount) => discoveryToMountTreeItem(mount));
            return {
              children: children as TreeItem[],
              pagination: {
                currentPage: 1,
                totalCount: children.length,
                hasMore: false,
              },
            };
          }

          const mountNode = parseMountTreeNodeId(treeId);
          if (mountNode) {
            return loadMountFolderChildren({
              mountId: mountNode.mountId,
              normalizedPath: mountNode.normalizedPath,
              parentId: treeId,
            });
          }

          // Extract the original item ID from the tree ID for API requests.
          // Tree IDs for favorites follow the format: `parentTreeId::itemId` (e.g., `favorites::abc123`)
          const originalId = getOriginalIdFromTreeId(treeId);
          const isFavoriteItem = treeId.startsWith(DefaultRoute.FAVORITES);

          if (originalId === DefaultRoute.FAVORITES) {
            const response = await driver.getFavoriteItems({
              page: page,
              type: ItemType.FOLDER,
            });

            const result = response.children.map((item) =>
              itemToTreeItem(item, treeId, true),
            ) as TreeItem[];

            return {
              children: result,
              pagination: response.pagination,
            };
          }
          const data = await driver.getChildren(originalId, {
            page: page,
            type: ItemType.FOLDER,
          });
          const result = data.children.map((item) =>
            itemToTreeItem(item, treeId, isFavoriteItem),
          ) as TreeItem[];

          return {
            children: result,
            pagination: data.pagination,
          };
        }}
        onRefresh={async (treeId) => {
          if (isMountsTreeRootId(treeId)) {
            const mounts = await loadMountDiscoveries();
            return buildMountsTreeRoot(
              t("explorer.tree.mounts"),
              mounts.length,
            ) as unknown as Partial<TreeItem>;
          }

          const mountNode = parseMountTreeNodeId(treeId);
          if (mountNode) {
            const mounts = await loadMountDiscoveries();
            const currentMount = mounts.find(
              (mount) => mount.mount_id === mountNode.mountId,
            );

            if (mountNode.normalizedPath === "/") {
              if (!currentMount) {
                throw new Error(`Missing mount discovery for ${mountNode.mountId}`);
              }
              return discoveryToMountTreeItem(currentMount) as unknown as Partial<TreeItem>;
            }

            const browse = await driver.browseMount({
              mountId: mountNode.mountId,
              path: mountNode.normalizedPath,
              limit: 1,
              offset: 0,
            });

            if (!currentMount) {
              throw new Error(`Missing mount discovery for ${mountNode.mountId}`);
            }

            return entryToMountTreeItem({
              mountId: mountNode.mountId,
              entry: browse.entry,
              mountTitle: getMountTitle(currentMount),
              provider: currentMount.provider,
              parentId:
                browse.entry.normalized_path === "/"
                  ? DefaultRoute.MOUNTS
                  : getMountTreeNodeId(
                      mountNode.mountId,
                    getParentMountPath(browse.entry.normalized_path) || "/",
                    ),
            }) as unknown as Partial<TreeItem>;
          }

          const originalId = getOriginalIdFromTreeId(treeId);
          const isFavoriteItem = treeId.startsWith(DefaultRoute.FAVORITES);
          const item = await driver.getItem(originalId);
          // Extract parent tree ID from current tree ID
          const parentTreeId = treeId.includes("::")
            ? treeId.substring(0, treeId.lastIndexOf("::"))
            : undefined;
          return itemToTreeItem(
            item,
            parentTreeId,
            isFavoriteItem,
          ) as unknown as Partial<TreeItem>;
        }}
      >
        <TreeProviderInitializer loadMountDiscoveries={loadMountDiscoveries}>
          <ExplorerDndProvider>
            {isInitialized ? children : <SpinnerPage />}
          </ExplorerDndProvider>
        </TreeProviderInitializer>
      </TreeProvider>
      <input
        {...dropZone.getInputProps({
          webkitdirectory: "true",
          id: ITEM_IMPORT_FOLDERS_INPUT_ID,
          style: DROPZONE_INPUT_HIDDEN_STYLE,
        })}
      />
      <input
        {...dropZone.getInputProps({
          id: ITEM_IMPORT_FILES_INPUT_ID,
          style: DROPZONE_INPUT_HIDDEN_STYLE,
        })}
      />

      <Toaster />
    </GlobalExplorerContext.Provider>
  );
};

/**
 * Initializes the tree provider with the root items ( aka workspaces )
 */
const TreeProviderInitializer = ({
  children,
  loadMountDiscoveries,
}: {
  children: React.ReactNode;
  loadMountDiscoveries: () => Promise<
    Awaited<ReturnType<ReturnType<typeof getDriver>["getMountsDiscovery"]>>
  >;
}) => {
  const { setTreeIsInitialized } = useGlobalExplorer();
  const { t } = useTranslation();
  const { user } = useAuth();

  const treeContext = useTreeContext<TreeItem>();

  const initialTree = async () => {
    const items: TreeViewDataType<TreeItem>[] = [];

    const [response, mounts] = await Promise.all([
      getDriver().getFavoriteItems({
        page: 1,
        type: ItemType.FOLDER,
      }),
      loadMountDiscoveries(),
    ]);

    const favorites = response.children.map((item) =>
      itemToTreeItem(item, DefaultRoute.FAVORITES, true),
    );

    const favoritesNode: TreeViewDataType<TreeItem> = {
      id: DefaultRoute.FAVORITES,
      nodeType: TreeViewNodeTypeEnum.SIMPLE_NODE,
      childrenCount: favorites.length,
      children: favorites,
      label: t("explorer.tree.favorites"),
      pagination: response.pagination,
    };

    items.push(favoritesNode);
    items.push(buildMountsTreeRoot(t("explorer.tree.mounts"), mounts.length));
    treeContext?.treeData.resetTree(items);
    setTreeIsInitialized(true);
  };

  // TODO: Move to global tree context?
  useEffect(() => {
    if (!user) {
      return;
    }

    initialTree();
  }, [user]);

  return children;
};
