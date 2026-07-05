import { getDriver } from "@/features/config/Config";
import { ItemFilters } from "@/features/drivers/Driver";
import {
  ItemType,
  ItemUploadState,
  LinkReach,
  LinkRole,
  type Item,
} from "@/features/drivers/types";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";

import {
  getRootItems,
  useFavoriteItems,
  useFirstLevelItems,
  useInfiniteItemInvitations,
  useItem,
  useItemAccesses,
  useItems,
} from "../useQueries";

jest.mock("@/features/config/Config", () => ({
  getDriver: jest.fn(),
}));

jest.mock("@tanstack/react-query", () => ({
  useInfiniteQuery: jest.fn((config) => config),
  useQuery: jest.fn((config) => config),
}));

const mockedGetDriver = jest.mocked(getDriver);
const mockedUseQuery = jest.mocked(useQuery);
const mockedUseInfiniteQuery = jest.mocked(useInfiniteQuery);

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

describe("useQueries", () => {
  const getFavoriteItems = jest.fn();
  const getItemAccesses = jest.fn();
  const getItemInvitations = jest.fn();
  const getItems = jest.fn();
  const getItem = jest.fn();

  beforeEach(() => {
    mockedUseQuery.mockClear();
    mockedUseInfiniteQuery.mockClear();
    getFavoriteItems.mockReset();
    getItemAccesses.mockReset();
    getItemInvitations.mockReset();
    getItems.mockReset();
    getItem.mockReset();

    mockedGetDriver.mockReturnValue({
      getFavoriteItems,
      getItemAccesses,
      getItemInvitations,
      getItems,
      getItem,
    } as never);
  });

  it("wires favorite items query to the driver favorites endpoint", async () => {
    const expected = [buildItem("favorite-1")];
    getFavoriteItems.mockResolvedValue(expected);

    const query = useFavoriteItems() as unknown as {
      queryKey: string[];
      queryFn: () => Promise<Item[]>;
    };

    expect(query.queryKey).toEqual(["items", "favorites"]);
    await expect(query.queryFn()).resolves.toEqual(expected);
    expect(getFavoriteItems).toHaveBeenCalledWith();
  });

  it("wires item accesses query with non-cached semantics", async () => {
    const expected = [{ id: "access-1" }];
    getItemAccesses.mockResolvedValue(expected);

    const query = useItemAccesses("item-1") as unknown as {
      queryKey: string[];
      queryFn: () => Promise<typeof expected>;
      staleTime: number;
      gcTime: number;
    };

    expect(query.queryKey).toEqual(["itemAccesses", "item-1"]);
    expect(query.staleTime).toBe(0);
    expect(query.gcTime).toBe(0);
    await expect(query.queryFn()).resolves.toEqual(expected);
    expect(getItemAccesses).toHaveBeenCalledWith("item-1");
  });

  it("wires infinite invitations query with stable page progression", async () => {
    const page: { next: string | null; results: Array<{ id: string }> } = {
      next: "page-2",
      results: [{ id: "invite-1" }],
    };
    getItemInvitations.mockResolvedValue(page);

    const query = useInfiniteItemInvitations("item-1") as unknown as {
      queryKey: string[];
      queryFn: () => Promise<typeof page>;
      initialPageParam: number;
      getNextPageParam: (
        lastPage: typeof page,
        allPages: Array<typeof page>,
      ) => number | undefined;
    };

    expect(query.queryKey).toEqual(["itemInvitations", "item-1"]);
    expect(query.initialPageParam).toBe(1);
    await expect(query.queryFn()).resolves.toEqual(page);
    expect(getItemInvitations).toHaveBeenCalledWith("item-1");
    expect(query.getNextPageParam(page, [page])).toBe(2);
    expect(
      query.getNextPageParam({ ...page, next: null }, [page, page]),
    ).toBeUndefined();
  });

  it("wires first-level items query to root items without refetch churn", async () => {
    const expected = [buildItem("folder-1", { type: ItemType.FOLDER })];
    getItems.mockResolvedValue({ children: expected });

    const query = useFirstLevelItems() as unknown as {
      queryKey: string[];
      queryFn: () => Promise<Item[]>;
      refetchOnWindowFocus: boolean;
      refetchOnMount: boolean;
    };

    expect(query.queryKey).toEqual(["firstLevelItems"]);
    expect(query.refetchOnWindowFocus).toBe(false);
    expect(query.refetchOnMount).toBe(false);
    await expect(query.queryFn()).resolves.toEqual(expected);
    expect(getItems).toHaveBeenCalledWith(undefined);
  });

  it("wires root items query to the shared getRootItems helper", async () => {
    const expected = [buildItem("root-1", { type: ItemType.FOLDER })];
    getItems.mockResolvedValue({ children: expected });

    const query = useItems() as unknown as {
      queryKey: string[];
      queryFn: () => Promise<Item[]>;
    };

    expect(query.queryKey).toEqual(["items"]);
    await expect(query.queryFn()).resolves.toEqual(expected);
    expect(getItems).toHaveBeenCalledWith(undefined);
  });

  it("returns only root children from getRootItems and forwards filters", async () => {
    const expected = [buildItem("folder-1", { type: ItemType.FOLDER })];
    const filters = { type: ItemType.FOLDER } as ItemFilters;
    getItems.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      children: expected,
    });

    await expect(getRootItems(filters)).resolves.toEqual(expected);
    expect(getItems).toHaveBeenCalledWith(filters);
  });

  it("wires single-item query, preserves previous placeholder data and forwards options", async () => {
    const item = buildItem("item-1");
    getItem.mockResolvedValue(item);

    const query = useItem("item-1", {
      enabled: false,
      staleTime: 42,
    }) as unknown as {
      queryKey: string[];
      queryFn: () => Promise<Item>;
      enabled: boolean;
      staleTime: number;
      placeholderData: (previous?: Item) => Item | undefined;
    };

    expect(query.queryKey).toEqual(["items", "item-1"]);
    expect(query.enabled).toBe(false);
    expect(query.staleTime).toBe(42);
    await expect(query.queryFn()).resolves.toEqual(item);
    expect(getItem).toHaveBeenCalledWith("item-1");
    expect(query.placeholderData(item)).toBe(item);
    expect(query.placeholderData(undefined)).toBeUndefined();
  });
});
