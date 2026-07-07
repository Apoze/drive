import { LinkReach, LinkRole, Role } from "../../types";
import { StandardDriver } from "../StandardDriver";
import { fetchAPI } from "@/features/api/fetchApi";

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
  type: "file",
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

describe("StandardDriver lightweight REST adapters", () => {
  let driver: StandardDriver;

  beforeEach(() => {
    driver = new StandardDriver();
    mockedFetchAPI.mockReset();
  });

  it("routes user wrappers through the canonical endpoints", async () => {
    const users = [
      {
        id: "user-1",
        email: "jane@example.test",
        full_name: "Jane Doe",
        short_name: "JD",
        language: "en",
      },
    ];
    const contacts = [
      {
        id: "user-2",
        full_name: "John Doe",
        short_name: "JD",
      },
    ];
    const updatedUser = {
      id: "user-1",
      email: "jane@example.test",
      full_name: "Jane Doe",
      short_name: "JD",
      language: "fr",
    };
    mockedFetchAPI
      .mockResolvedValueOnce(makeResponse(users))
      .mockResolvedValueOnce(makeResponse(contacts))
      .mockResolvedValueOnce(makeResponse(updatedUser));

    await expect(driver.getUsers({ q: "jane" })).resolves.toEqual(users);
    await expect(driver.getContacts()).resolves.toEqual(contacts);
    await expect(
      driver.updateUser({ id: "user-1", language: "fr" }),
    ).resolves.toEqual(updatedUser);

    expect(mockedFetchAPI).toHaveBeenNthCalledWith(1, "users/", {
      params: { q: "jane" },
    });
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(2, "users/contacts/", {
      params: undefined,
    });
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(3, "users/user-1/", {
      method: "PATCH",
      body: JSON.stringify({ id: "user-1", language: "fr" }),
    });
  });

  it("routes access wrappers and keeps the 204 updateAccess branch void", async () => {
    const accesses = [{ id: "access-1", role: Role.READER }];
    mockedFetchAPI
      .mockResolvedValueOnce(makeResponse(accesses))
      .mockResolvedValueOnce(makeResponse({}, 201))
      .mockResolvedValueOnce(makeResponse({}, 204))
      .mockResolvedValueOnce(makeResponse({}, 204))
      .mockResolvedValueOnce(makeResponse({}, 204));

    await expect(driver.getItemAccesses("item-1")).resolves.toEqual(accesses);
    await expect(
      driver.createAccess({
        itemId: "item-1",
        userId: "user-2",
        role: Role.EDITOR,
      }),
    ).resolves.toBeUndefined();
    await expect(
      driver.deleteAccess({ itemId: "item-1", accessId: "access-1" }),
    ).resolves.toBeUndefined();
    await expect(
      driver.updateLinkConfiguration({
        itemId: "item-1",
        link_reach: LinkReach.PUBLIC,
        link_role: LinkRole.EDITOR,
      }),
    ).resolves.toBeUndefined();
    await expect(
      driver.updateAccess({
        itemId: "item-1",
        accessId: "access-1",
        user_id: "user-2",
        role: Role.READER,
      }),
    ).resolves.toBeUndefined();

    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      1,
      "items/item-1/accesses/",
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(2, "items/item-1/accesses/", {
      method: "POST",
      body: JSON.stringify({
        user_id: "user-2",
        role: Role.EDITOR,
      }),
    });
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      3,
      "items/item-1/accesses/access-1/",
      {
        method: "DELETE",
      },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      4,
      "items/item-1/link-configuration/",
      {
        method: "PUT",
        body: JSON.stringify({
          link_reach: LinkReach.PUBLIC,
          link_role: LinkRole.EDITOR,
        }),
      },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      5,
      "items/item-1/accesses/access-1/",
      {
        method: "PATCH",
        body: JSON.stringify({
          user_id: "user-2",
          role: Role.READER,
        }),
      },
    );
  });

  it("returns the JSON payload when updateAccess does not answer 204", async () => {
    const updatedAccess = { id: "access-1", role: Role.EDITOR };
    mockedFetchAPI.mockResolvedValueOnce(makeResponse(updatedAccess, 200));

    await expect(
      driver.updateAccess({
        itemId: "item-1",
        accessId: "access-1",
        user_id: "user-2",
        role: Role.EDITOR,
      }),
    ).resolves.toEqual(updatedAccess);
  });

  it("routes invitation wrappers with the current payload contracts", async () => {
    const invitation = {
      id: "invitation-1",
      email: "guest@example.test",
      role: Role.READER,
    };
    const invitationList = {
      count: 1,
      next: null,
      previous: null,
      results: [invitation],
    };
    const updatedInvitation = {
      ...invitation,
      role: Role.EDITOR,
    };
    mockedFetchAPI
      .mockResolvedValueOnce(makeResponse(invitation, 201))
      .mockResolvedValueOnce(makeResponse({}, 204))
      .mockResolvedValueOnce(makeResponse(updatedInvitation))
      .mockResolvedValueOnce(makeResponse(invitationList));

    await expect(
      driver.createInvitation({
        itemId: "item-1",
        email: "guest@example.test",
        role: Role.READER,
      }),
    ).resolves.toEqual(invitation);
    await expect(
      driver.deleteInvitation({
        itemId: "item-1",
        invitationId: "invitation-1",
      }),
    ).resolves.toBeUndefined();
    await expect(
      driver.updateInvitation({
        itemId: "item-1",
        invitationId: "invitation-1",
        role: Role.EDITOR,
      }),
    ).resolves.toEqual(updatedInvitation);
    await expect(driver.getItemInvitations("item-1")).resolves.toEqual(
      invitationList,
    );

    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      1,
      "items/item-1/invitations/",
      {
        method: "POST",
        body: JSON.stringify({
          email: "guest@example.test",
          role: Role.READER,
        }),
      },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      2,
      "items/item-1/invitations/invitation-1/",
      {
        method: "DELETE",
      },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      3,
      "items/item-1/invitations/invitation-1/",
      {
        method: "PATCH",
        body: JSON.stringify({
          itemId: "item-1",
          invitationId: "invitation-1",
          role: Role.EDITOR,
        }),
      },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      4,
      "items/item-1/invitations/",
    );
  });

  it("maps recent items through jsonToItems and derives pagination", async () => {
    mockedFetchAPI.mockResolvedValueOnce(
      makeResponse({
        count: 3,
        next: "http://api.example.test/api/v1.0/items/recents/?page=2",
        previous: null,
        results: [
          buildItemJson(),
          buildItemJson({
            id: "item-2",
            updated_at: "2026-03-31T09:15:00.000Z",
          }),
        ],
      }),
    );

    const result = await driver.getRecentItems({
      page: 2,
      ordering: "-updated_at",
    });

    expect(mockedFetchAPI).toHaveBeenCalledWith("items/recents/", {
      params: {
        page: 2,
        ordering: "-updated_at",
        page_size: 200,
      },
    });
    expect(result.pagination).toEqual({
      currentPage: 2,
      totalCount: 3,
      hasMore: true,
    });
    expect(result.children).toHaveLength(2);
    expect(result.children[0]?.updated_at).toBeInstanceOf(Date);
    expect(result.children[1]?.updated_at).toBeInstanceOf(Date);
  });

  it("maps favorite items and favorite mutations through the canonical endpoints", async () => {
    mockedFetchAPI
      .mockResolvedValueOnce(
        makeResponse({
          count: 1,
          next: null,
          previous: null,
          results: [buildItemJson({ id: "favorite-1" })],
        }),
      )
      .mockResolvedValueOnce(makeResponse({}, 201))
      .mockResolvedValueOnce(makeResponse({}, 204));

    const result = await driver.getFavoriteItems({ page: 1 });
    await expect(driver.createFavoriteItem("favorite-1")).resolves.toBeUndefined();
    await expect(driver.deleteFavoriteItem("favorite-1")).resolves.toBeUndefined();

    expect(mockedFetchAPI).toHaveBeenNthCalledWith(1, "items/favorite_list/", {
      params: {
        page: 1,
        page_size: 200,
      },
    });
    expect(result.pagination).toEqual({
      currentPage: 1,
      totalCount: 1,
      hasMore: false,
    });
    expect(result.children[0]?.updated_at).toBeInstanceOf(Date);
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      2,
      "items/favorite-1/favorite/",
      {
        method: "POST",
      },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      3,
      "items/favorite-1/favorite/",
      {
        method: "DELETE",
      },
    );
  });

  it("keeps entitlements and mounts discovery as simple JSON wrappers", async () => {
    const entitlements = {
      can_access: { result: true },
      can_upload: { result: false, message: "forbidden" },
    };
    const discovery = [
      {
        mount_id: "mount-1",
        display_name: "Shared Docs",
        provider: "localfs",
        capabilities: {
          "mount.preview": true,
        },
      },
    ];
    mockedFetchAPI
      .mockResolvedValueOnce(makeResponse(entitlements))
      .mockResolvedValueOnce(makeResponse(discovery));

    await expect(driver.getEntitlements()).resolves.toEqual(entitlements);
    await expect(driver.getMountsDiscovery()).resolves.toEqual(discovery);

    expect(mockedFetchAPI).toHaveBeenNthCalledWith(1, "entitlements/");
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(2, "mounts/");
  });
});
