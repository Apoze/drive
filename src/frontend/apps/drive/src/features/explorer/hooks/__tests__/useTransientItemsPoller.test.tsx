import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useQueryClient, useQueries } from "@tanstack/react-query";
import { getDriver } from "@/features/config/Config";
import { APIError } from "@/features/api/APIError";
import { ItemType, ItemUploadState, type Item } from "@/features/drivers/types";
import { addToast } from "@/features/ui/components/toaster/Toaster";
import { useRemoveItemsFromPaginatedList } from "../useOptimisticPagination";
import { useRefreshItemCache } from "../useRefreshItems";
import { useTransientItemsPoller } from "../useTransientItemsPoller";

jest.mock("@/features/config/Config", () => ({
  getDriver: jest.fn(),
}));

jest.mock("@/features/api/APIError", () => ({
  APIError: class APIError extends Error {
    code: number;
    data?: unknown;

    constructor(code: number, data?: unknown) {
      super();
      this.code = code;
      this.data = data;
    }
  },
}));

jest.mock("@tanstack/react-query", () => ({
  useQueries: jest.fn(),
  useQueryClient: jest.fn(),
}));

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  addToast: jest.fn(),
  ToasterItem: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

jest.mock("../useOptimisticPagination", () => ({
  useRemoveItemsFromPaginatedList: jest.fn(),
}));

jest.mock("../useRefreshItems", () => ({
  useRefreshItemCache: jest.fn(),
}));

const mockedGetDriver = jest.mocked(getDriver);
const mockedUseQueries = jest.mocked(useQueries);
const mockedUseQueryClient = jest.mocked(useQueryClient);
const mockedUseRefreshItemCache = jest.mocked(useRefreshItemCache);
const mockedUseRemoveItemsFromPaginatedList = jest.mocked(
  useRemoveItemsFromPaginatedList,
);
const mockedAddToast = jest.mocked(addToast);

const buildItem = (
  id: string,
  uploadState: ItemUploadState = ItemUploadState.READY,
): Item =>
  ({
    id,
    title: id,
    filename: `${id}.txt`,
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
    upload_state: uploadState,
    updated_at: new Date("2026-03-23T00:00:00Z"),
    description: "",
    created_at: new Date("2026-03-23T00:00:00Z"),
    path: `/${id}.txt`,
    abilities: {},
  }) as Item;

type PollQuery = {
  queryKey: unknown[];
  queryFn: () => Promise<Item | null>;
  refetchInterval: (query: {
    state: { data: Item | null | undefined };
  }) => number | false;
};

describe("useTransientItemsPoller", () => {
  const refreshItemCache = jest.fn();
  const removeItems = jest.fn();
  const removeQueries = jest.fn();
  const getItem = jest.fn();

  const renderPoller = (items: Item[]) => {
    const Harness = () => {
      useTransientItemsPoller(items);
      return null;
    };
    renderToStaticMarkup(<Harness />);
    return (mockedUseQueries.mock.calls[0][0] as { queries: PollQuery[] })
      .queries;
  };

  beforeEach(() => {
    refreshItemCache.mockReset();
    removeItems.mockReset();
    removeQueries.mockReset();
    getItem.mockReset();
    mockedUseQueries.mockReset();
    mockedAddToast.mockReset();
    mockedUseRefreshItemCache.mockReturnValue(refreshItemCache);
    mockedUseRemoveItemsFromPaginatedList.mockReturnValue(removeItems);
    mockedUseQueryClient.mockReturnValue({ removeQueries } as never);
    mockedGetDriver.mockReturnValue({ getItem } as never);
  });

  it("polls every shared transient upload state with the shared query key", () => {
    const queries = renderPoller([
      buildItem("duplicating", ItemUploadState.DUPLICATING),
      buildItem("converting", ItemUploadState.CONVERTING),
      buildItem("analyzing", ItemUploadState.ANALYZING),
      buildItem("ready", ItemUploadState.READY),
    ]);

    expect(queries.map((query) => query.queryKey)).toEqual([
      ["items", "duplicating", "transient-poll"],
      ["items", "converting", "transient-poll"],
      ["items", "analyzing", "transient-poll"],
    ]);
  });

  it("refreshes a transient item when polling returns a terminal item", async () => {
    const readyItem = buildItem("duplicating", ItemUploadState.READY);
    getItem.mockResolvedValueOnce(readyItem);

    const [query] = renderPoller([
      buildItem("duplicating", ItemUploadState.DUPLICATING),
    ]);

    await expect(query.queryFn()).resolves.toBe(readyItem);

    expect(getItem).toHaveBeenCalledWith("duplicating");
    expect(refreshItemCache).toHaveBeenCalledWith("duplicating", readyItem);
    expect(
      query.refetchInterval({ state: { data: readyItem } }),
    ).toBe(false);
  });

  it("removes a missing transient item and shows one conversion failure toast", async () => {
    getItem.mockRejectedValue(new APIError(404, "Missing"));

    const [query] = renderPoller([
      buildItem("converting", ItemUploadState.CONVERTING),
    ]);

    await expect(query.queryFn()).resolves.toBeNull();
    await expect(query.queryFn()).resolves.toBeNull();

    expect(removeItems).toHaveBeenCalledWith(["items"], ["converting"]);
    expect(removeQueries).toHaveBeenCalledWith({
      queryKey: ["items", "converting"],
    });
    expect(mockedAddToast).toHaveBeenCalledTimes(1);
    expect(query.refetchInterval({ state: { data: null } })).toBe(false);
  });
});
