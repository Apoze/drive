import { getDriver } from "@/features/config/Config";
import {
  ItemType,
  ItemUploadState,
  LinkReach,
  LinkRole,
  type Item,
  WorkspaceType,
} from "@/features/drivers/types";
import { DefaultRoute } from "@/utils/defaultRoutes";

import {
  clearFromRoute,
  formatSize,
  getExtension,
  getExtensionFromName,
  getFromRoute,
  getItemTitle,
  getLastVisitedItem,
  getManualNavigationItemId,
  getParentIdFromPath,
  getWorkspaceType,
  gotoLastVisitedItem,
  isIdInItemTree,
  itemToPreviewFile,
  setFromRoute,
  setManualNavigationItemId,
  timeAgo,
} from "../utils";

jest.mock("@/features/config/Config", () => ({
  getDriver: jest.fn(),
}));

jest.mock("@/features/i18n/initI18n", () => ({
  __esModule: true,
  default: {
    t: (key: string, options?: { count?: number }) =>
      options?.count ? `${key}:${options.count}` : key,
  },
}));

const mockedGetDriver = jest.mocked(getDriver);

const buildItem = (id: string, overrides: Partial<Item> = {}): Item => ({
  id,
  title: `Item ${id}`,
  filename: `Item-${id}.txt`,
  creator: {
    id: "owner-1",
    full_name: "Owner",
    short_name: "OW",
  },
  type: ItemType.FILE,
  ancestors_link_reach: null,
  ancestors_link_role: null,
  computed_link_reach: LinkReach.RESTRICTED,
  computed_link_role: LinkRole.READER,
  upload_state: ItemUploadState.READY,
  updated_at: new Date("2026-03-31T00:00:00Z"),
  description: "",
  created_at: new Date("2026-03-31T00:00:00Z"),
  path: `root.${id}`,
  abilities: {
    accesses_manage: false,
    accesses_view: true,
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
    partial_update: true,
    restore: false,
    retrieve: true,
    tree: false,
    update: true,
    upload_ended: true,
  },
  ...overrides,
});

describe("explorer utils", () => {
  const getItems = jest.fn();
  const originalWindow = global.window;
  const originalSessionStorage = global.sessionStorage;

  beforeEach(() => {
    getItems.mockReset();
    mockedGetDriver.mockReturnValue({
      getItems,
    } as never);
    Object.defineProperty(global, "window", {
      configurable: true,
      value: {
        location: {
          href: "http://192.168.10.123:3000/explorer/items/my-files",
        },
      },
    });
    Object.defineProperty(global, "sessionStorage", {
      configurable: true,
      value: {
        data: {} as Record<string, string>,
        setItem(key: string, value: string) {
          this.data[key] = value;
        },
        getItem(key: string) {
          return this.data[key] ?? null;
        },
        removeItem(key: string) {
          delete this.data[key];
        },
        clear() {
          this.data = {};
        },
      },
    });
  });

  afterEach(() => {
    jest.useRealTimers();
    if (originalWindow === undefined) {
      Object.defineProperty(global, "window", {
        configurable: true,
        value: undefined,
      });
    } else {
      Object.defineProperty(global, "window", {
        configurable: true,
        value: originalWindow,
      });
    }
    if (originalSessionStorage === undefined) {
      Object.defineProperty(global, "sessionStorage", {
        configurable: true,
        value: undefined,
      });
    } else {
      Object.defineProperty(global, "sessionStorage", {
        configurable: true,
        value: originalSessionStorage,
      });
    }
  });

  it("stores and clears the route breadcrumb in session storage", () => {
    expect(getFromRoute()).toBeNull();

    setFromRoute(DefaultRoute.MY_FILES);
    expect(getFromRoute()).toBe(DefaultRoute.MY_FILES);

    clearFromRoute();
    expect(getFromRoute()).toBeNull();
  });

  it("stores and reads the manual navigation item id in session storage", () => {
    expect(getManualNavigationItemId()).toBeNull();

    setManualNavigationItemId("item-42");

    expect(getManualNavigationItemId()).toBe("item-42");
  });

  it("returns the main workspace first when resolving the last visited item", async () => {
    const secondary = buildItem("folder-1", { type: ItemType.FOLDER });
    const main = buildItem("folder-2", {
      type: ItemType.FOLDER,
      main_workspace: true,
    });
    getItems.mockResolvedValue({
      children: [secondary, main],
    });

    await expect(getLastVisitedItem()).resolves.toBe(main);
    expect(getItems).toHaveBeenCalledWith({ type: ItemType.FOLDER });
  });

  it("falls back to the first folder and returns null when no folder exists", async () => {
    const first = buildItem("folder-1", { type: ItemType.FOLDER });
    getItems.mockResolvedValueOnce({
      children: [first, buildItem("folder-2", { type: ItemType.FOLDER })],
    });
    await expect(getLastVisitedItem()).resolves.toBe(first);

    getItems.mockResolvedValueOnce({ children: [] });
    await expect(getLastVisitedItem()).resolves.toBeNull();
  });

  it("redirects to the last visited item and logs a clear error when none exists", async () => {
    getItems.mockResolvedValueOnce({
      children: [buildItem("folder-1", { type: ItemType.FOLDER })],
    });

    await gotoLastVisitedItem("/prefix");
    expect(global.window.location.href).toBe("/prefix/explorer/items/folder-1");

    const consoleErrorSpy = jest
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    getItems.mockResolvedValueOnce({ children: [] });

    await gotoLastVisitedItem();

    expect(consoleErrorSpy).toHaveBeenCalledWith(
      "No items found, so cannot redirect to last visited item",
    );
    expect(global.window.location.href).toBe("/prefix/explorer/items/folder-1");
    consoleErrorSpy.mockRestore();
  });

  it("formats relative time across the supported buckets", () => {
    jest.useFakeTimers().setSystemTime(new Date("2026-03-31T12:00:00Z"));

    expect(timeAgo(new Date("2025-02-24T12:00:00Z"))).toBe("time.years_ago:1");
    expect(timeAgo(new Date("2026-01-15T12:00:00Z"))).toBe("time.months_ago:2");
    expect(timeAgo(new Date("2026-03-10T12:00:00Z"))).toBe("time.weeks_ago:3");
    expect(timeAgo(new Date("2026-03-29T12:00:00Z"))).toBe("time.days_ago:2");
    expect(timeAgo(new Date("2026-03-31T09:00:00Z"))).toBe("time.hours_ago:3");
    expect(timeAgo(new Date("2026-03-31T11:57:00Z"))).toBe(
      "time.minutes_ago:3",
    );
    expect(timeAgo(new Date("2026-03-31T11:59:59Z"))).toBe("time.seconds_ago");
  });

  it("extracts extensions from filename or title and tolerates missing names", () => {
    const item = buildItem("item-1", {
      filename: "report.pdf",
      title: "report.final.docx",
    });

    expect(getExtension(item)).toBe("pdf");
    expect(getExtension(item, true)).toBe("docx");
    expect(getExtensionFromName("archive.tar.gz")).toBe("gz");
    expect(getExtensionFromName("no-extension")).toBeNull();
    expect(getExtensionFromName("")).toBeNull();
  });

  it("formats byte sizes with the project rounding rules", () => {
    expect(formatSize(500)).toBe("500 B");
    expect(formatSize(1536)).toBe("1.54 KB");
    expect(formatSize(10 * 1024)).toBe("10.2 KB");
    expect(formatSize(123 * 1024)).toBe("126 KB");
  });

  it("formats byte sizes with translated units when available", () => {
    const t = (key: string) => `translated:${key}`;

    expect(formatSize(1536, t)).toBe(
      "1.54 translated:explorer.grid.size_units.KB",
    );
  });

  it("extracts the parent id from an item path", () => {
    expect(getParentIdFromPath("root.parent.child")).toBe("parent");
    expect(getParentIdFromPath("root")).toBeUndefined();
    expect(getParentIdFromPath(undefined)).toBeUndefined();
  });

  it("derives the workspace type from main/public/shared semantics", () => {
    expect(
      getWorkspaceType(buildItem("main", { main_workspace: true })),
    ).toBe(WorkspaceType.MAIN);
    expect(
      getWorkspaceType(
        buildItem("public", {
          link_reach: LinkReach.PUBLIC,
          user_roles: [],
        }),
      ),
    ).toBe(WorkspaceType.PUBLIC);
    expect(getWorkspaceType(buildItem("shared"))).toBe(WorkspaceType.SHARED);
  });

  it("checks tree membership through path ids", () => {
    expect(isIdInItemTree("root.parent.child", "parent")).toBe(true);
    expect(isIdInItemTree("root.parent.child", "missing")).toBe(false);
    expect(isIdInItemTree("", "parent")).toBe(false);
    expect(isIdInItemTree("root.parent.child", "")).toBe(false);
  });

  it("uses the translated main workspace title and keeps regular item titles", () => {
    expect(
      getItemTitle(buildItem("main", { main_workspace: true, title: "Ignored" })),
    ).toBe("explorer.workspaces.mainWorkspace");
    expect(getItemTitle(buildItem("file-1", { title: "Visible title" }))).toBe(
      "Visible title",
    );
  });

  it("maps an item to the preview file contract with the right fallbacks", () => {
    const suspiciousPreview = itemToPreviewFile(
      buildItem("file-1", {
        title: "Image",
        filename: "image.jpg",
        mimetype: undefined,
        url: "/download/file-1",
        url_preview: "/preview/file-1",
        is_wopi_supported: true,
        size: 1234,
        upload_state: ItemUploadState.SUSPICIOUS,
        abilities: {
          ...buildItem("template").abilities,
          update: false,
        },
      }),
    );

    expect(suspiciousPreview).toEqual({
      id: "file-1",
      title: "Image",
      filename: "image.jpg",
      mimetype: "",
      url_preview: "/preview/file-1",
      url: "/download/file-1",
      isSuspicious: true,
      is_wopi_supported: true,
      size: 1234,
      can_update: false,
    });
  });
});
