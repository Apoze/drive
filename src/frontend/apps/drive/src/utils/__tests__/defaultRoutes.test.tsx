import {
  DefaultRoute,
  ORDERED_DEFAULT_ROUTES,
  TRASH_ROUTE_DATA,
  getDefaultRoute,
  getDefaultRouteId,
  getMyFilesQueryKey,
  getQueryKeyForRouteId,
  getRecentItemsQueryKey,
  getSharedWithMeQueryKey,
  isDefaultRoute,
  isMyFilesRoute,
} from "../defaultRoutes";

describe("defaultRoutes", () => {
  it("keeps the canonical ordered default route ids", () => {
    expect(ORDERED_DEFAULT_ROUTES.map((route) => route.id)).toEqual([
      DefaultRoute.RECENT,
      DefaultRoute.MY_FILES,
      DefaultRoute.SHARED_WITH_ME,
      DefaultRoute.FAVORITES,
      DefaultRoute.MOUNTS,
    ]);
  });

  it("resolves default and trash routes from pathnames", () => {
    expect(getDefaultRoute("/explorer/items/my-files")).toEqual(
      expect.objectContaining({
        id: DefaultRoute.MY_FILES,
        route: "/explorer/items/my-files",
      }),
    );
    expect(getDefaultRoute("/explorer/trash")).toEqual(TRASH_ROUTE_DATA);
    expect(getDefaultRoute("/explorer/items/files/item-1")).toBeUndefined();
  });

  it("derives ids and predicates from route pathnames", () => {
    expect(getDefaultRouteId("/explorer/mounts")).toBe(DefaultRoute.MOUNTS);
    expect(isDefaultRoute("/explorer/items/recent")).toBe(true);
    expect(isDefaultRoute("/explorer/items/files")).toBe(false);
    expect(isMyFilesRoute("/explorer/items/my-files")).toBe(true);
    expect(isMyFilesRoute("/explorer/mounts")).toBe(false);
  });

  it("keeps the canonical query keys", () => {
    expect(getMyFilesQueryKey()).toEqual([
      "items",
      "infinite",
      JSON.stringify({ is_creator_me: true }),
    ]);
    expect(getRecentItemsQueryKey()).toEqual(["items", "infinite"]);
    expect(getSharedWithMeQueryKey()).toEqual([
      "items",
      "infinite",
      JSON.stringify({ is_creator_me: false }),
    ]);
  });

  it("returns the expected query key for each supported default route", () => {
    expect(getQueryKeyForRouteId("/explorer/items/my-files")).toEqual(
      getMyFilesQueryKey(),
    );
    expect(getQueryKeyForRouteId("/explorer/items/recent")).toEqual(
      getRecentItemsQueryKey(),
    );
    expect(getQueryKeyForRouteId("/explorer/items/shared-with-me")).toEqual(
      getSharedWithMeQueryKey(),
    );
    expect(getQueryKeyForRouteId("/explorer/mounts")).toEqual([]);
    expect(getQueryKeyForRouteId("/explorer/trash")).toEqual([]);
  });
});
