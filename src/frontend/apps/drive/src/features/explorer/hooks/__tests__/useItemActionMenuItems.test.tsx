import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  ItemType,
  ItemUploadState,
  LinkReach,
  LinkRole,
  type Item,
} from "@/features/drivers/types";
import { useItemActionMenuItems } from "../useItemActionMenuItems";
import {
  itemToTreeItem,
  useGlobalExplorer,
} from "@/features/explorer/components/GlobalExplorerContext";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { DefaultRoute } from "@/utils/defaultRoutes";

const mockTreeAddChild = jest.fn();
const mockDeleteItems = jest.fn();
const mockCreateFavoriteMutateAsync = jest.fn();
const mockDeleteFavoriteMutateAsync = jest.fn();
const mockDuplicateMutateAsync = jest.fn();
const mockAddToast = jest.fn();

jest.mock("i18next", () => ({
  t: (key: string) => key,
}));

jest.mock("next/router", () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
}));

jest.mock("../../utils/utils", () => ({
  getParentIdFromPath: jest.fn(() => "parent-1"),
  setManualNavigationItemId: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  useTreeContext: () => ({
    treeData: {
      addChild: mockTreeAddChild,
    },
  }),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  useModal: jest.fn(),
}));

jest.mock("@/features/explorer/components/GlobalExplorerContext", () => ({
  itemToTreeItem: jest.fn(),
  useGlobalExplorer: jest.fn(),
}));

jest.mock("@/features/items/hooks/useDownloadItem", () => ({
  useDownloadItem: () => ({
    handleDownloadItem: jest.fn(),
  }),
}));

jest.mock("../useDeleteItem", () => ({
  useDeleteItem: () => ({
    deleteItems: mockDeleteItems,
  }),
}));

jest.mock("../useMutations", () => ({
  useMutationCreateFavoriteItem: () => ({
    mutateAsync: mockCreateFavoriteMutateAsync,
  }),
  useMutationDeleteFavoriteItem: () => ({
    mutateAsync: mockDeleteFavoriteMutateAsync,
  }),
  useMutationDuplicateItem: () => ({
    mutateAsync: mockDuplicateMutateAsync,
  }),
}));

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  addToast: (...args: unknown[]) => mockAddToast(...args),
  ToasterItem: ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

jest.mock(
  "@/features/explorer/components/modals/ExplorerRenameItemModal",
  () => ({
    ExplorerRenameItemModal: () => null,
  }),
);

jest.mock("@/features/explorer/components/modals/share/ItemShareModal", () => ({
  ItemShareModal: () => null,
}));

jest.mock("@/features/explorer/components/modals/ExplorerUnzipModal", () => ({
  ExplorerUnzipModal: () => null,
}));

jest.mock("@/features/explorer/components/modals/ConvertLegacyFileModal", () => ({
  ConvertLegacyFileModal: () => null,
}));

jest.mock(
  "@/features/explorer/components/modals/move/ExplorerMoveFolderModal",
  () => ({
    ExplorerMoveFolder: () => null,
  }),
);

const mockedUseGlobalExplorer = jest.mocked(useGlobalExplorer);
const mockedUseModal = jest.mocked(useModal);
const mockedItemToTreeItem = jest.mocked(itemToTreeItem);

const buildItem = (overrides: Partial<Item> = {}): Item => ({
  id: "item-1",
  title: "Report",
  filename: "Report.txt",
  creator: {
    id: "user-1",
    full_name: "Jane Doe",
    short_name: "JD",
  },
  type: ItemType.FILE,
  ancestors_link_reach: null,
  ancestors_link_role: null,
  computed_link_reach: null,
  computed_link_role: null,
  upload_state: ItemUploadState.READY,
  updated_at: new Date("2026-03-22T00:00:00Z"),
  description: "",
  created_at: new Date("2026-03-22T00:00:00Z"),
  path: "/Report.txt",
  mimetype: "text/plain",
  link_reach: LinkReach.RESTRICTED,
  link_role: LinkRole.READER,
  abilities: {
    accesses_manage: false,
    accesses_view: true,
    children_create: false,
    children_list: false,
    duplicate: true,
    destroy: true,
    favorite: false,
    invite_owner: false,
    link_configuration: false,
    media_auth: false,
    move: true,
    link_select_options: {
      [LinkReach.RESTRICTED]: null,
      [LinkReach.AUTHENTICATED]: null,
      [LinkReach.PUBLIC]: null,
    },
    partial_update: false,
    restore: false,
    retrieve: true,
    tree: false,
    update: true,
    upload_ended: false,
  },
  ...overrides,
});

describe("useItemActionMenuItems", () => {
  beforeEach(() => {
    mockCreateFavoriteMutateAsync.mockReset();
    mockCreateFavoriteMutateAsync.mockImplementation(
      async (_itemId: string, options?: { onSuccess?: () => void }) => {
        options?.onSuccess?.();
      },
    );
    mockDeleteFavoriteMutateAsync.mockReset();
    mockDuplicateMutateAsync.mockReset();
    mockAddToast.mockReset();
    mockDeleteItems.mockReset();
    mockTreeAddChild.mockReset();
    mockedItemToTreeItem.mockReset();
    mockedItemToTreeItem.mockReturnValue({ id: "favorite-tree-item" } as never);
    mockedUseModal.mockReset();
    mockedUseModal
      .mockReturnValueOnce({
        isOpen: false,
        open: jest.fn(),
        close: jest.fn(),
      } as never)
      .mockReturnValueOnce({
        isOpen: false,
        open: jest.fn(),
        close: jest.fn(),
      } as never)
      .mockReturnValueOnce({
        isOpen: false,
        open: jest.fn(),
        close: jest.fn(),
      } as never)
      .mockReturnValueOnce({
        isOpen: false,
        open: jest.fn(),
        close: jest.fn(),
      } as never)
      .mockReturnValueOnce({
        isOpen: false,
        open: jest.fn(),
        close: jest.fn(),
      } as never);
  });

  it("routes the info action through the explicit right-panel API", () => {
    const openRightPanelForItem = jest.fn();
    const item = buildItem();
    let capturedGetMenuItems:
      ReturnType<typeof useItemActionMenuItems>["getMenuItems"] | undefined;

    mockedUseGlobalExplorer.mockReturnValue({
      openRightPanelForItem,
      item,
    } as never);

    const Harness = () => {
      capturedGetMenuItems = useItemActionMenuItems().getMenuItems;
      return null;
    };

    renderToStaticMarkup(<Harness />);

    const infoAction = capturedGetMenuItems
      ? capturedGetMenuItems(item).find(
          (action) =>
            "label" in action &&
            action.label === "explorer.item.actions.view_info",
        )
      : undefined;

    if (infoAction && "callback" in infoAction) {
      infoAction.callback?.();
    }

    expect(infoAction).toBeDefined();
    expect(openRightPanelForItem).toHaveBeenCalledWith(item);
  });

  it("keeps the folder shared actions in the canonical convergence order", () => {
    const item = buildItem({
      type: ItemType.FOLDER,
      filename: "Folder",
      title: "Folder",
      path: "/Folder",
      abilities: {
        ...buildItem().abilities,
        export: true,
      },
    });
    let capturedGetMenuItems:
      ReturnType<typeof useItemActionMenuItems>["getMenuItems"] | undefined;

    mockedUseGlobalExplorer.mockReturnValue({
      openRightPanelForItem: jest.fn(),
      item,
    } as never);

    const Harness = () => {
      capturedGetMenuItems = useItemActionMenuItems().getMenuItems;
      return null;
    };

    renderToStaticMarkup(<Harness />);

    const visibleLabels =
      capturedGetMenuItems?.(item, { minimal: false }).flatMap((action) =>
        "label" in action && !action.isHidden ? [action.label] : [],
      ) ?? [];

    expect(visibleLabels).toEqual([
      "explorer.item.actions.share",
      "explorer.item.actions.download",
      "explorer.item.actions.favorite",
      "explorer.item.actions.rename",
      "explorer.item.actions.move",
      "explorer.item.actions.view_info",
      "explorer.item.actions.delete",
    ]);
  });

  it("hides folder download when export ability is absent", () => {
    const item = buildItem({
      type: ItemType.FOLDER,
      filename: "Folder",
      title: "Folder",
      path: "/Folder",
      abilities: {
        ...buildItem().abilities,
        export: false,
      },
    });
    let capturedGetMenuItems:
      ReturnType<typeof useItemActionMenuItems>["getMenuItems"] | undefined;

    mockedUseGlobalExplorer.mockReturnValue({
      openRightPanelForItem: jest.fn(),
      item,
    } as never);

    const Harness = () => {
      capturedGetMenuItems = useItemActionMenuItems().getMenuItems;
      return null;
    };

    renderToStaticMarkup(<Harness />);

    const downloadActions =
      capturedGetMenuItems?.(item).filter(
        (action) =>
          "label" in action &&
          action.label === "explorer.item.actions.download",
      ) ?? [];

    expect(downloadActions).toHaveLength(2);
    expect(
      downloadActions.every((action) => "isHidden" in action && action.isHidden),
    ).toBe(true);
  });

  it("exposes unzip only for readable zip files", () => {
    const item = buildItem({
      filename: "archive.zip",
      title: "archive.zip",
      type: ItemType.FILE,
    });
    let capturedGetMenuItems:
      ReturnType<typeof useItemActionMenuItems>["getMenuItems"] | undefined;

    mockedUseGlobalExplorer.mockReturnValue({
      openRightPanelForItem: jest.fn(),
      item,
    } as never);

    const Harness = () => {
      capturedGetMenuItems = useItemActionMenuItems().getMenuItems;
      return null;
    };

    renderToStaticMarkup(<Harness />);

    const unzipAction = capturedGetMenuItems
      ? capturedGetMenuItems(item).find(
          (action) =>
            "label" in action && action.label === "explorer.item.actions.unzip",
        )
      : undefined;

    expect(unzipAction).toMatchObject({
      isHidden: false,
    });
  });

  it("duplicates regular files through the item duplicate mutation", async () => {
    mockDuplicateMutateAsync.mockResolvedValue(undefined);
    const item = buildItem();
    let capturedGetMenuItems:
      ReturnType<typeof useItemActionMenuItems>["getMenuItems"] | undefined;

    mockedUseGlobalExplorer.mockReturnValue({
      openRightPanelForItem: jest.fn(),
      item,
    } as never);

    const Harness = () => {
      capturedGetMenuItems = useItemActionMenuItems().getMenuItems;
      return null;
    };

    renderToStaticMarkup(<Harness />);

    const duplicateAction = capturedGetMenuItems
      ? capturedGetMenuItems(item).find(
          (action) =>
            "label" in action &&
            action.label === "explorer.item.actions.duplicate",
        )
      : undefined;

    expect(duplicateAction).toMatchObject({
      isHidden: false,
    });
    if (duplicateAction && "callback" in duplicateAction) {
      await duplicateAction.callback?.();
    }

    expect(mockDuplicateMutateAsync).toHaveBeenCalledWith("item-1");
    expect(mockAddToast).not.toHaveBeenCalled();
  });

  it("hides duplicate for folders and files without duplicate ability", () => {
    const folder = buildItem({
      type: ItemType.FOLDER,
      filename: "Folder",
      title: "Folder",
      path: "/Folder",
    });
    const fileWithoutAbility = buildItem({
      abilities: {
        ...buildItem().abilities,
        duplicate: false,
      },
    });
    let capturedGetMenuItems:
      ReturnType<typeof useItemActionMenuItems>["getMenuItems"] | undefined;

    mockedUseGlobalExplorer.mockReturnValue({
      openRightPanelForItem: jest.fn(),
      item: folder,
    } as never);

    const Harness = () => {
      capturedGetMenuItems = useItemActionMenuItems().getMenuItems;
      return null;
    };

    renderToStaticMarkup(<Harness />);

    const folderDuplicateAction = capturedGetMenuItems
      ? capturedGetMenuItems(folder).find(
          (action) =>
            "label" in action &&
            action.label === "explorer.item.actions.duplicate",
        )
      : undefined;
    const noAbilityDuplicateAction = capturedGetMenuItems
      ? capturedGetMenuItems(fileWithoutAbility).find(
          (action) =>
            "label" in action &&
            action.label === "explorer.item.actions.duplicate",
        )
      : undefined;

    expect(folderDuplicateAction).toMatchObject({ isHidden: true });
    expect(noAbilityDuplicateAction).toMatchObject({ isHidden: true });
  });

  it("shows a focused duplicate error toast when duplicate fails", async () => {
    mockDuplicateMutateAsync.mockRejectedValue(new Error("boom"));
    const item = buildItem();
    let capturedGetMenuItems:
      ReturnType<typeof useItemActionMenuItems>["getMenuItems"] | undefined;

    mockedUseGlobalExplorer.mockReturnValue({
      openRightPanelForItem: jest.fn(),
      item,
    } as never);

    const Harness = () => {
      capturedGetMenuItems = useItemActionMenuItems().getMenuItems;
      return null;
    };

    renderToStaticMarkup(<Harness />);

    const duplicateAction = capturedGetMenuItems
      ? capturedGetMenuItems(item).find(
          (action) =>
            "label" in action &&
            action.label === "explorer.item.actions.duplicate",
        )
      : undefined;

    if (duplicateAction && "callback" in duplicateAction) {
      await duplicateAction.callback?.();
    }

    expect(mockAddToast).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ type: "error" }),
    );
  });

  it("opens explicit conversion from the regular file action menu", () => {
    const shareModal = {
      isOpen: false,
      open: jest.fn(),
      close: jest.fn(),
    };
    const renameModal = {
      isOpen: false,
      open: jest.fn(),
      close: jest.fn(),
    };
    const moveModal = {
      isOpen: false,
      open: jest.fn(),
      close: jest.fn(),
    };
    const unzipModal = {
      isOpen: false,
      open: jest.fn(),
      close: jest.fn(),
    };
    const convertModal = {
      isOpen: false,
      open: jest.fn(),
      close: jest.fn(),
    };
    const item = buildItem({
      filename: "legacy.doc",
      title: "legacy.doc",
      abilities: {
        ...buildItem().abilities,
        convert: true,
      },
    });
    let capturedGetMenuItems:
      ReturnType<typeof useItemActionMenuItems>["getMenuItems"] | undefined;

    mockedUseModal.mockReset();
    mockedUseModal
      .mockReturnValueOnce(shareModal as never)
      .mockReturnValueOnce(renameModal as never)
      .mockReturnValueOnce(moveModal as never)
      .mockReturnValueOnce(unzipModal as never)
      .mockReturnValueOnce(convertModal as never);
    mockedUseGlobalExplorer.mockReturnValue({
      openRightPanelForItem: jest.fn(),
      item,
    } as never);

    const Harness = () => {
      capturedGetMenuItems = useItemActionMenuItems().getMenuItems;
      return null;
    };

    renderToStaticMarkup(<Harness />);

    const convertAction = capturedGetMenuItems
      ? capturedGetMenuItems(item).find(
          (action) =>
            "label" in action && action.label === "explorer.item.actions.convert",
        )
      : undefined;

    expect(convertAction).toMatchObject({ isHidden: false });
    if (convertAction && "callback" in convertAction) {
      convertAction.callback?.();
    }

    expect(convertModal.open).toHaveBeenCalled();
  });

  it("hides conversion for folders, minimal menus, and files without ability", () => {
    const folder = buildItem({
      type: ItemType.FOLDER,
      filename: "Folder",
      title: "Folder",
      path: "/Folder",
      abilities: {
        ...buildItem().abilities,
        convert: true,
      },
    });
    const fileWithoutAbility = buildItem({
      abilities: {
        ...buildItem().abilities,
        convert: false,
      },
    });
    const fileWithAbility = buildItem({
      abilities: {
        ...buildItem().abilities,
        convert: true,
      },
    });
    let capturedGetMenuItems:
      ReturnType<typeof useItemActionMenuItems>["getMenuItems"] | undefined;

    mockedUseGlobalExplorer.mockReturnValue({
      openRightPanelForItem: jest.fn(),
      item: folder,
    } as never);

    const Harness = () => {
      capturedGetMenuItems = useItemActionMenuItems().getMenuItems;
      return null;
    };

    renderToStaticMarkup(<Harness />);

    const getConvertAction = (
      item: Item,
      options?: Parameters<
        ReturnType<typeof useItemActionMenuItems>["getMenuItems"]
      >[1],
    ) =>
      capturedGetMenuItems
        ? capturedGetMenuItems(item, options).find(
            (action) =>
              "label" in action &&
              action.label === "explorer.item.actions.convert",
          )
        : undefined;

    expect(getConvertAction(folder)).toMatchObject({ isHidden: true });
    expect(getConvertAction(fileWithoutAbility)).toMatchObject({
      isHidden: true,
    });
    expect(getConvertAction(fileWithAbility, { minimal: true })).toMatchObject({
      isHidden: true,
    });
  });

  it("hides unzip when the item is not eligible for archive extraction", () => {
    const item = buildItem({
      abilities: {
        ...buildItem().abilities,
        retrieve: false,
      },
      filename: "archive.zip",
      title: "archive.zip",
      type: ItemType.FILE,
    });
    let capturedGetMenuItems:
      ReturnType<typeof useItemActionMenuItems>["getMenuItems"] | undefined;

    mockedUseGlobalExplorer.mockReturnValue({
      openRightPanelForItem: jest.fn(),
      item,
    } as never);

    const Harness = () => {
      capturedGetMenuItems = useItemActionMenuItems().getMenuItems;
      return null;
    };

    renderToStaticMarkup(<Harness />);

    const unzipAction = capturedGetMenuItems
      ? capturedGetMenuItems(item, { minimal: true }).find(
          (action) =>
            "label" in action && action.label === "explorer.item.actions.unzip",
        )
      : undefined;

    expect(unzipAction).toMatchObject({
      isHidden: true,
    });
  });

  it("opens the share modal through the shared single-item launcher", () => {
    const shareModal = {
      isOpen: false,
      open: jest.fn(),
      close: jest.fn(),
    };
    const renameModal = {
      isOpen: false,
      open: jest.fn(),
      close: jest.fn(),
    };
    const moveModal = {
      isOpen: false,
      open: jest.fn(),
      close: jest.fn(),
    };
    const unzipModal = {
      isOpen: false,
      open: jest.fn(),
      close: jest.fn(),
    };
    const convertModal = {
      isOpen: false,
      open: jest.fn(),
      close: jest.fn(),
    };
    const item = buildItem();
    let capturedGetMenuItems:
      ReturnType<typeof useItemActionMenuItems>["getMenuItems"] | undefined;

    mockedUseModal.mockReset();
    mockedUseModal
      .mockReturnValueOnce(shareModal as never)
      .mockReturnValueOnce(renameModal as never)
      .mockReturnValueOnce(moveModal as never)
      .mockReturnValueOnce(unzipModal as never)
      .mockReturnValueOnce(convertModal as never);
    mockedUseGlobalExplorer.mockReturnValue({
      openRightPanelForItem: jest.fn(),
      item,
    } as never);

    const Harness = () => {
      capturedGetMenuItems = useItemActionMenuItems().getMenuItems;
      return null;
    };

    renderToStaticMarkup(<Harness />);

    const shareAction = capturedGetMenuItems
      ? capturedGetMenuItems(item).find(
          (action) =>
            "label" in action && action.label === "explorer.item.actions.share",
        )
      : undefined;

    if (shareAction && "callback" in shareAction) {
      shareAction.callback?.();
    }

    expect(shareModal.open).toHaveBeenCalled();
  });

  it("opens the move modal through the shared single-item launcher", () => {
    const shareModal = {
      isOpen: false,
      open: jest.fn(),
      close: jest.fn(),
    };
    const renameModal = {
      isOpen: false,
      open: jest.fn(),
      close: jest.fn(),
    };
    const moveModal = {
      isOpen: false,
      open: jest.fn(),
      close: jest.fn(),
    };
    const unzipModal = {
      isOpen: false,
      open: jest.fn(),
      close: jest.fn(),
    };
    const convertModal = {
      isOpen: false,
      open: jest.fn(),
      close: jest.fn(),
    };
    const item = buildItem();
    let capturedGetMenuItems:
      ReturnType<typeof useItemActionMenuItems>["getMenuItems"] | undefined;

    mockedUseModal.mockReset();
    mockedUseModal
      .mockReturnValueOnce(shareModal as never)
      .mockReturnValueOnce(renameModal as never)
      .mockReturnValueOnce(moveModal as never)
      .mockReturnValueOnce(unzipModal as never)
      .mockReturnValueOnce(convertModal as never);
    mockedUseGlobalExplorer.mockReturnValue({
      openRightPanelForItem: jest.fn(),
      item,
    } as never);

    const Harness = () => {
      capturedGetMenuItems = useItemActionMenuItems().getMenuItems;
      return null;
    };

    renderToStaticMarkup(<Harness />);

    const moveAction = capturedGetMenuItems
      ? capturedGetMenuItems(item).find(
          (action) =>
            "label" in action && action.label === "explorer.item.actions.move",
        )
      : undefined;

    if (moveAction && "callback" in moveAction) {
      moveAction.callback?.();
    }

    expect(moveModal.open).toHaveBeenCalled();
  });

  it("routes favorite through the shared favorite command and tree sync", async () => {
    const item = buildItem({
      type: ItemType.FOLDER,
    });
    let capturedGetMenuItems:
      ReturnType<typeof useItemActionMenuItems>["getMenuItems"] | undefined;

    mockedUseGlobalExplorer.mockReturnValue({
      openRightPanelForItem: jest.fn(),
      item,
    } as never);

    const Harness = () => {
      capturedGetMenuItems = useItemActionMenuItems().getMenuItems;
      return null;
    };

    renderToStaticMarkup(<Harness />);

    const favoriteAction = capturedGetMenuItems
      ? capturedGetMenuItems(item).find(
          (action) =>
            "label" in action &&
            action.label === "explorer.item.actions.favorite",
        )
      : undefined;

    if (favoriteAction && "callback" in favoriteAction) {
      await favoriteAction.callback?.();
    }

    expect(mockCreateFavoriteMutateAsync).toHaveBeenCalledWith(
      "item-1",
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
    expect(mockedItemToTreeItem).toHaveBeenCalledWith(
      item,
      DefaultRoute.FAVORITES,
      true,
    );
    expect(mockTreeAddChild).toHaveBeenCalledWith(DefaultRoute.FAVORITES, {
      id: "favorite-tree-item",
    });
  });
});
