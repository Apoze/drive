import { ItemType } from "../../types";
import { StandardDriver } from "../StandardDriver";
import { fetchAPI } from "@/features/api/fetchApi";
import { BatchDeleteError } from "@/features/errors/BatchDeleteError";
import { BatchOperationError } from "@/features/errors/BatchOperationError";

jest.mock("@/features/api/fetchApi", () => ({
  ensureCsrfCookie: jest.fn(),
  fetchAPI: jest.fn(),
  getCSRFToken: jest.fn(),
}));

const mockedFetchAPI = jest.mocked(fetchAPI);

const makeResponse = <T>(data: T, status = 200) =>
  ({
    status,
    json: jest.fn().mockResolvedValue(data),
    headers: {
      get: jest.fn().mockReturnValue(null),
    },
  }) as never;

const buildItemJson = (overrides: Record<string, unknown> = {}) => ({
  id: "item-1",
  title: "Quarterly report",
  filename: "Quarterly report.pdf",
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
  upload_state: "ready",
  updated_at: "2026-03-31T08:00:00.000Z",
  description: "",
  created_at: "2026-03-30T08:00:00.000Z",
  path: "/Quarterly report.pdf",
  mimetype: "application/pdf",
  link_reach: "restricted",
  link_role: "reader",
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
      restricted: null,
      authenticated: null,
      public: null,
    },
    partial_update: false,
    restore: false,
    retrieve: true,
    tree: false,
    update: false,
    upload_ended: false,
  },
  ...overrides,
});

describe("StandardDriver items/tree/create adapters", () => {
  let driver: StandardDriver;

  beforeEach(() => {
    driver = new StandardDriver();
    mockedFetchAPI.mockReset();
  });

  it("maps getItems and getChildren through jsonToItems with derived pagination", async () => {
    mockedFetchAPI
      .mockResolvedValueOnce(
        makeResponse({
          count: 3,
          next: "http://api.example.test/api/v1.0/items/?page=2",
          previous: null,
          results: [
            buildItemJson(),
            buildItemJson({
              id: "item-2",
              updated_at: "2026-03-31T09:15:00.000Z",
            }),
          ],
        }),
      )
      .mockResolvedValueOnce(
        makeResponse({
          count: 1,
          next: null,
          previous: null,
          results: [buildItemJson({ id: "child-1" })],
        }),
      );

    const items = await driver.getItems({ page: 2, page_size: 50 });
    const children = await driver.getChildren("parent-1", {
      page: 3,
      page_size: 25,
    });

    expect(mockedFetchAPI).toHaveBeenNthCalledWith(1, "items/", {
      params: {
        page: 2,
        page_size: 50,
        ordering: "-type,-created_at",
      },
    });
    expect(items.pagination).toEqual({
      currentPage: 2,
      totalCount: 3,
      hasMore: true,
    });
    expect(items.children[0]?.updated_at).toBeInstanceOf(Date);

    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      2,
      "items/parent-1/children/",
      {
        params: {
          page: 3,
          page_size: 25,
          ordering: "-type,-created_at",
        },
      },
    );
    expect(children.pagination).toEqual({
      currentPage: 3,
      totalCount: 1,
      hasMore: false,
    });
    expect(children.children[0]?.updated_at).toBeInstanceOf(Date);
  });

  it("keeps breadcrumb, search and trash wrappers on their canonical endpoints", async () => {
    const breadcrumb = [
      {
        id: "root",
        title: "Root",
        path: "root",
        depth: 0,
        main_workspace: true,
      },
    ];
    mockedFetchAPI
      .mockResolvedValueOnce(makeResponse(breadcrumb))
      .mockResolvedValueOnce(
        makeResponse({
          results: [buildItemJson({ id: "search-1" })],
        }),
      )
      .mockResolvedValueOnce(
        makeResponse({
          results: [buildItemJson({ id: "trash-1" })],
        }),
      );

    await expect(driver.getItemBreadcrumb("item-1")).resolves.toEqual(breadcrumb);
    await expect(driver.searchItems({ title: "report" })).resolves.toMatchObject([
      expect.objectContaining({ id: "search-1", updated_at: expect.any(Date) }),
    ]);
    await expect(driver.getTrashItems({ ordering: "-updated_at" })).resolves.toMatchObject([
      expect.objectContaining({ id: "trash-1", updated_at: expect.any(Date) }),
    ]);

    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      1,
      "items/item-1/breadcrumb/",
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(2, "items/search/", {
      params: { title: "report" },
    });
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(3, "items/trashbin/", {
      params: {
        ordering: "-updated_at",
        page_size: 200,
      },
    });
  });

  it("maps getItem, updateItem and getTree through jsonToItem recursively", async () => {
    const nestedChild = buildItemJson({
      id: "child-1",
      updated_at: "2026-03-31T09:00:00.000Z",
    });
    const nestedItem = buildItemJson({
      id: "item-tree",
      updated_at: "2026-03-31T10:00:00.000Z",
      children: [nestedChild],
    });
    mockedFetchAPI
      .mockResolvedValueOnce(makeResponse(nestedItem))
      .mockResolvedValueOnce(makeResponse(nestedItem))
      .mockResolvedValueOnce(makeResponse(nestedItem));

    const item = await driver.getItem("item-tree");
    const updated = await driver.updateItem({
      id: "item-tree",
      title: "Renamed",
    });
    const tree = await driver.getTree("item-tree");

    expect(mockedFetchAPI).toHaveBeenNthCalledWith(1, "items/item-tree/");
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(2, "items/item-tree/", {
      method: "PATCH",
      body: JSON.stringify({
        id: "item-tree",
        title: "Renamed",
      }),
    });
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(3, "items/item-tree/tree/");
    expect(item.updated_at).toBeInstanceOf(Date);
    expect(item.children?.[0]?.updated_at).toBeInstanceOf(Date);
    expect(updated.updated_at).toBeInstanceOf(Date);
    expect(tree.children?.[0]?.updated_at).toBeInstanceOf(Date);
  });

  it("keeps move and restore wrappers sequential", async () => {
    mockedFetchAPI
      .mockResolvedValueOnce(makeResponse({}, 204))
      .mockResolvedValueOnce(makeResponse({}, 204))
      .mockResolvedValueOnce(makeResponse({}, 204));

    await expect(driver.moveItem("item-1", "parent-2")).resolves.toBeUndefined();

    expect(mockedFetchAPI).toHaveBeenNthCalledWith(1, "items/item-1/move/", {
      method: "POST",
      body: JSON.stringify({ target_item_id: "parent-2" }),
    }, {
      redirectOn40x: false,
    });

    const moveItemSpy = jest
      .spyOn(driver, "moveItem")
      .mockResolvedValue(undefined);

    await expect(driver.moveItems(["item-1", "item-2"], "parent-2")).resolves.toBeUndefined();
    await expect(driver.restoreItems(["item-1", "item-2", "item-3"])).resolves.toBeUndefined();

    expect(moveItemSpy).toHaveBeenNthCalledWith(1, "item-1", "parent-2");
    expect(moveItemSpy).toHaveBeenNthCalledWith(2, "item-2", "parent-2");
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      2,
      "items/item-1/restore/",
      { method: "POST" },
      { redirectOn40x: false },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      3,
      "items/item-2/restore/",
      { method: "POST" },
      { redirectOn40x: false },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      4,
      "items/item-3/restore/",
      { method: "POST" },
      { redirectOn40x: false },
    );
  });

  it("routes creation wrappers with the current payloads and jsonToItem mapping", async () => {
    mockedFetchAPI
      .mockResolvedValueOnce(makeResponse(buildItemJson({ id: "folder-1" }), 201))
      .mockResolvedValueOnce(
        makeResponse(buildItemJson({ id: "workspace-1", type: ItemType.FOLDER }), 201),
      )
      .mockResolvedValueOnce(makeResponse(buildItemJson({ id: "odf-1" }), 201))
      .mockResolvedValueOnce(makeResponse(buildItemJson({ id: "new-file-1" }), 201));

    const folder = await driver.createFolder({
      parentId: "parent-1",
      title: "Projects",
    });
    const workspace = await driver.createWorkspace({
      title: "Workspace",
      description: "Shared",
    });
    const odf = await driver.createOdfDocument({
      parentId: "parent-1",
      kind: "odt",
      filename: "Doc.odt",
    });
    const newFile = await driver.createNewFile({
      parentId: "parent-1",
      filenameStem: "Budget",
      extension: "ods",
      kind: "sheet",
    });

    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      1,
      "items/parent-1/children/",
      {
        method: "POST",
        body: JSON.stringify({
          title: "Projects",
          type: ItemType.FOLDER,
        }),
      },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(2, "items/", {
      method: "POST",
      body: JSON.stringify({
        title: "Workspace",
        description: "Shared",
        type: ItemType.FOLDER,
      }),
    });
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(3, "items/new-odf/", {
      method: "POST",
      body: JSON.stringify({
        parent_id: "parent-1",
        kind: "odt",
        filename: "Doc.odt",
      }),
    });
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(4, "items/new-file/", {
      method: "POST",
      body: JSON.stringify({
        parent_id: "parent-1",
        filename_stem: "Budget",
        extension: "ods",
        kind: "sheet",
      }),
    });
    expect(folder.updated_at).toBeInstanceOf(Date);
    expect(workspace.updated_at).toBeInstanceOf(Date);
    expect(odf.updated_at).toBeInstanceOf(Date);
    expect(newFile.updated_at).toBeInstanceOf(Date);
  });

  it("delegates updateWorkspace and deleteWorkspace to the existing item wrappers", async () => {
    const updatedWorkspace = buildItemJson({ id: "workspace-1" });
    const updateItemSpy = jest
      .spyOn(driver, "updateItem")
      .mockResolvedValue(updatedWorkspace as never);
    const deleteItemsSpy = jest
      .spyOn(driver, "deleteItems")
      .mockResolvedValue(undefined);

    await expect(
      driver.updateWorkspace({ id: "workspace-1", title: "Workspace" } as never),
    ).resolves.toEqual(updatedWorkspace);
    await expect(driver.deleteWorkspace("workspace-1")).resolves.toBeUndefined();

    expect(updateItemSpy).toHaveBeenCalledWith({
      id: "workspace-1",
      title: "Workspace",
    });
    expect(deleteItemsSpy).toHaveBeenCalledWith(["workspace-1"]);
  });

  it("keeps delete and hard-delete wrappers sequential", async () => {
    mockedFetchAPI
      .mockResolvedValueOnce(makeResponse({}, 204))
      .mockResolvedValueOnce(makeResponse({}, 204))
      .mockResolvedValueOnce(makeResponse({}, 204))
      .mockResolvedValueOnce(makeResponse({}, 204));

    await expect(driver.deleteItems(["item-1", "item-2"])).resolves.toBeUndefined();
    await expect(
      driver.hardDeleteItems(["item-1", "item-2"]),
    ).resolves.toBeUndefined();

    expect(mockedFetchAPI).toHaveBeenNthCalledWith(1, "items/item-1/", {
      method: "DELETE",
    }, {
      redirectOn40x: false,
    });
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(2, "items/item-2/", {
      method: "DELETE",
    }, {
      redirectOn40x: false,
    });
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      3,
      "items/item-1/hard-delete/",
      { method: "DELETE" },
      { redirectOn40x: false },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      4,
      "items/item-2/hard-delete/",
      { method: "DELETE" },
      { redirectOn40x: false },
    );
  });

  it("surfaces partial bulk delete failures without triggering a global redirect contract", async () => {
    const apiError = new Error("403");
    mockedFetchAPI
      .mockResolvedValueOnce(makeResponse({}, 204))
      .mockRejectedValueOnce(apiError);

    await expect(driver.deleteItems(["item-1", "item-2"])).rejects.toMatchObject({
      name: "BatchDeleteError",
      completedIds: ["item-1"],
      failedId: "item-2",
      cause: apiError,
    } satisfies Partial<BatchDeleteError>);

    expect(mockedFetchAPI).toHaveBeenNthCalledWith(1, "items/item-1/", {
      method: "DELETE",
    }, {
      redirectOn40x: false,
    });
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(2, "items/item-2/", {
      method: "DELETE",
    }, {
      redirectOn40x: false,
    });
  });

  it("surfaces partial restore, hard-delete and move failures without a global redirect contract", async () => {
    const apiError = new Error("403");
    mockedFetchAPI
      .mockResolvedValueOnce(makeResponse({}, 204))
      .mockRejectedValueOnce(apiError)
      .mockResolvedValueOnce(makeResponse({}, 204))
      .mockRejectedValueOnce(apiError);

    await expect(driver.restoreItems(["item-1", "item-2"])).rejects.toMatchObject({
      name: "BatchOperationError",
      completedIds: ["item-1"],
      failedId: "item-2",
      cause: apiError,
    } satisfies Partial<BatchOperationError>);

    await expect(
      driver.hardDeleteItems(["item-1", "item-2"]),
    ).rejects.toMatchObject({
      name: "BatchOperationError",
      completedIds: ["item-1"],
      failedId: "item-2",
      cause: apiError,
    } satisfies Partial<BatchOperationError>);

    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      1,
      "items/item-1/restore/",
      { method: "POST" },
      { redirectOn40x: false },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      2,
      "items/item-2/restore/",
      { method: "POST" },
      { redirectOn40x: false },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      3,
      "items/item-1/hard-delete/",
      { method: "DELETE" },
      { redirectOn40x: false },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      4,
      "items/item-2/hard-delete/",
      { method: "DELETE" },
      { redirectOn40x: false },
    );

    const moveItemSpy = jest
      .spyOn(driver, "moveItem")
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(apiError);

    await expect(driver.moveItems(["item-1", "item-2"], "parent-2")).rejects.toMatchObject({
      name: "BatchOperationError",
      completedIds: ["item-1"],
      failedId: "item-2",
      cause: apiError,
    } satisfies Partial<BatchOperationError>);

    expect(moveItemSpy).toHaveBeenNthCalledWith(1, "item-1", "parent-2");
    expect(moveItemSpy).toHaveBeenNthCalledWith(2, "item-2", "parent-2");
  });
});
