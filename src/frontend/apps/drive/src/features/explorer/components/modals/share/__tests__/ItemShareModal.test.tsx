import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  ItemType,
  ItemUploadState,
  LinkReach,
  LinkRole,
  Role,
  type Access,
  type Invitation,
  type Item,
  type User,
} from "@/features/drivers/types";
import { ItemShareModal } from "../ItemShareModal";

type CapturedShareModalProps = {
  modalTitle?: React.ReactNode;
  children?: React.ReactNode;
  outsideSearchContent?: React.ReactNode;
  onInviteUser: (users: User[], role: Role) => Promise<void>;
  accesses: Access[];
  accessRoleTopMessage: (access: Access) => React.ReactNode;
  topLinkReachMessage?: React.ReactNode;
  onUpdateLinkRole: (role: LinkRole) => void;
  onUpdateLinkReach: (reach: LinkReach) => void;
};

type CapturedCopyFooterProps = {
  onCopyLink: () => void | Promise<void>;
};

const capturedShareModalProps: CapturedShareModalProps[] = [];
const capturedCopyFooterProps: CapturedCopyFooterProps[] = [];
const invalidateQueries = jest.fn();
const copyToClipboard = jest.fn();
const createAccess = jest.fn();
const createInvitation = jest.fn();
const updateAccess = jest.fn();
const deleteAccess = jest.fn();
const deleteInvitation = jest.fn();
const updateInvitation = jest.fn();
const mutateUpdateLinkConfiguration = jest.fn();
const errorToString = jest.fn((error: unknown) => String(error));
const addToast = jest.fn();
const push = jest.fn(() => Promise.resolve(true));
const posthogCapture = jest.fn();
const refetchItem = jest.fn();

let mockedItem: Item;
let mockedAccesses: Access[] | undefined;
let mockedInvitations:
  | { pages: Array<{ results: Invitation[] }> }
  | undefined;
let mockedUsers: User[] | undefined;
let mockedUserId = "owner-1";

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  HorizontalSeparator: () => <div>separator</div>,
  ShareModal: (props: CapturedShareModalProps) => {
    capturedShareModalProps.push(props);
    return (
      <div data-testid="share-modal">
        {String(props.modalTitle)}
        {props.children as React.ReactNode}
        {props.outsideSearchContent as React.ReactNode}
      </div>
    );
  },
  ShareModalCopyLinkFooter: (props: CapturedCopyFooterProps) => {
    capturedCopyFooterProps.push(props);
    return <div data-testid="copy-footer">copy-footer</div>;
  },
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({
    invalidateQueries,
  }),
}));

jest.mock("next/router", () => ({
  useRouter: () => ({
    push,
  }),
}));

jest.mock("@/features/auth/Auth", () => ({
  useAuth: () => ({
    user: { id: mockedUserId },
  }),
}));

jest.mock("@/features/explorer/hooks/useQueries", () => ({
  useItem: () => ({
    data: mockedItem,
    refetch: refetchItem,
  }),
  useItemAccesses: () => ({
    data: mockedAccesses,
  }),
  useInfiniteItemInvitations: () => ({
    data: mockedInvitations,
    hasNextPage: false,
  }),
}));

jest.mock("@/features/users/hooks/useUserQueries", () => ({
  useUsers: () => ({
    data: mockedUsers,
    isLoading: false,
  }),
}));

jest.mock("@/hooks/useCopyToClipboard", () => ({
  useClipboard: () => copyToClipboard,
}));

jest.mock("@/features/explorer/hooks/useMutationsAccesses", () => ({
  useMutationCreateAccess: () => ({ mutateAsync: createAccess }),
  useMutationCreateInvitation: () => ({ mutateAsync: createInvitation }),
  useMutationUpdateAccess: () => ({ mutateAsync: updateAccess }),
  useMutationDeleteAccess: () => ({ mutateAsync: deleteAccess }),
  useMutationDeleteInvitation: () => ({ mutateAsync: deleteInvitation }),
  useMutationUpdateInvitation: () => ({ mutateAsync: updateInvitation }),
}));

jest.mock("@/features/explorer/hooks/useMutations", () => ({
  useMutationUpdateLinkConfiguration: () => ({
    mutate: mutateUpdateLinkConfiguration,
  }),
}));

jest.mock("@/features/explorer/utils/mimeTypes", () => ({
  removeFileExtension: (value: string) => value.replace(/\.[^.]+$/, ""),
}));

jest.mock("@/features/api/APIError", () => {
  class APIError extends Error {
    code: number;
    data?: unknown;

    constructor(code: number, data?: unknown) {
      super();
      this.code = code;
      this.data = data;
    }
  }

  return {
    APIError,
    errorToString: (error: unknown) => errorToString(error),
  };
});

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  addToast: (...args: unknown[]) => addToast(...args),
  ToasterItem: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock("posthog-js", () => ({
  __esModule: true,
  default: {
    capture: (...args: unknown[]) => posthogCapture(...args),
  },
}));

const buildItem = (overrides: Partial<Item> = {}): Item => ({
  id: "item-1",
  title: "Report.pdf",
  filename: "Report.pdf",
  share_url: "https://share.example.test/item-1",
  creator: {
    id: "owner-1",
    full_name: "Owner User",
    short_name: "OU",
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
  path: "root.parent.item-1",
  size: 123,
  mimetype: "application/pdf",
  link_reach: LinkReach.RESTRICTED,
  link_role: LinkRole.READER,
  abilities: {
    accesses_manage: true,
    accesses_view: true,
    children_create: false,
    children_list: false,
    destroy: false,
    favorite: false,
    invite_owner: false,
    link_configuration: true,
    media_auth: false,
    move: false,
    link_select_options: {
      [LinkReach.RESTRICTED]: null,
      [LinkReach.AUTHENTICATED]: [LinkRole.READER, LinkRole.EDITOR],
      [LinkReach.PUBLIC]: [LinkRole.READER],
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

const buildAccess = (overrides: Partial<Access> = {}): Access => ({
  id: "access-1",
  role: Role.READER,
  team: "",
  user: {
    id: "user-1",
    email: "user-1@example.test",
    full_name: "Jane Doe",
    short_name: "JD",
    language: "en",
  },
  is_explicit: true,
  max_role: Role.READER,
  max_ancestors_role: Role.READER,
  max_ancestors_role_item_id: "parent-1",
  item: {
    id: "item-1",
    path: "root.parent.item-1",
    depth: 2,
  },
  abilities: {
    destroy: true,
    partial_update: true,
    retrieve: true,
    set_role_to: [Role.EDITOR, Role.ADMIN, Role.OWNER],
    update: true,
  },
  ...overrides,
});

const renderModal = () => {
  capturedShareModalProps.length = 0;
  capturedCopyFooterProps.length = 0;
  return renderToStaticMarkup(
    <ItemShareModal
      isOpen={true}
      onClose={jest.fn()}
      item={mockedItem}
    />,
  );
};

describe("ItemShareModal", () => {
  const originalWindow = global.window;

  beforeEach(() => {
    invalidateQueries.mockReset();
    copyToClipboard.mockReset();
    createAccess.mockReset();
    createInvitation.mockReset();
    updateAccess.mockReset();
    deleteAccess.mockReset();
    deleteInvitation.mockReset();
    updateInvitation.mockReset();
    mutateUpdateLinkConfiguration.mockReset();
    errorToString.mockReset();
    errorToString.mockImplementation((error: unknown) => String(error));
    addToast.mockReset();
    push.mockClear();
    posthogCapture.mockReset();
    refetchItem.mockReset();
    refetchItem.mockResolvedValue({ data: mockedItem });
    mockedUserId = "owner-1";
    mockedItem = buildItem();
    mockedAccesses = [buildAccess()];
    mockedInvitations = {
      pages: [{ results: [] }],
    };
    mockedUsers = [];
    Object.defineProperty(global, "window", {
      configurable: true,
      value: {
        location: {
          origin: "http://drive.example.test",
        },
      },
    });
  });

  afterEach(() => {
    Object.defineProperty(global, "window", {
      configurable: true,
      value: originalWindow,
    });
  });

  it("splits invitation email vs user access and falls back to updateAccess when already in this item", async () => {
    const existingAccess = buildAccess({
      id: "access-existing",
      user: {
        id: "user-2",
        email: "user-2@example.test",
        full_name: "Existing User",
        short_name: "EU",
        language: "en",
      },
    });
    mockedAccesses = [existingAccess];
    const { APIError } = jest.requireMock("@/features/api/APIError") as {
      APIError: new (code: number, data?: unknown) => Error;
    };
    createAccess.mockRejectedValueOnce(new APIError(409));
    updateAccess.mockResolvedValue(undefined);
    createInvitation.mockResolvedValue(undefined);
    errorToString.mockReturnValue("already in this item");

    renderModal();
    const shareModalProps = capturedShareModalProps[0]!;
    const accessUser = {
      id: "user-2",
      email: "user-2@example.test",
      full_name: "Existing User",
      short_name: "EU",
      language: "en",
    };
    const invitationUser = {
      id: "guest@example.test",
      email: "guest@example.test",
      full_name: "Guest",
      short_name: "GU",
      language: "en",
    };

    await shareModalProps.onInviteUser([accessUser, invitationUser], Role.EDITOR);

    expect(createAccess).toHaveBeenCalledWith({
      itemId: "item-1",
      userId: "user-2",
      role: Role.EDITOR,
    });
    expect(updateAccess).toHaveBeenCalledWith({
      itemId: "item-1",
      accessId: "access-existing",
      role: Role.EDITOR,
      user_id: "user-2",
    });
    expect(createInvitation).toHaveBeenCalledWith({
      itemId: "item-1",
      email: "guest@example.test",
      role: Role.EDITOR,
    });
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["itemAccesses", "item-1"],
    });
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["itemInvitations", "item-1"],
    });
  });

  it("deduplicates accesses in favor of the explicit one and exposes inherited redirection messages", () => {
    const implicit = buildAccess({
      id: "access-implicit",
      is_explicit: false,
      abilities: {
        ...buildAccess().abilities,
        destroy: false,
        set_role_to: [],
      },
      max_role: Role.READER,
      max_ancestors_role: Role.ADMIN,
      max_ancestors_role_item_id: "parent-99",
    });
    const explicit = buildAccess({
      id: "access-explicit",
      is_explicit: true,
      user: implicit.user,
    });
    mockedAccesses = [implicit, explicit];
    mockedItem = buildItem({
      abilities: {
        ...buildItem().abilities,
        link_configuration: false,
      },
    });

    renderModal();
    const shareModalProps = capturedShareModalProps[0]!;

    expect(shareModalProps.accesses).toHaveLength(1);
    expect(shareModalProps.accesses[0]).toMatchObject({
      id: "access-explicit",
      is_explicit: true,
    });
    expect(
      renderToStaticMarkup(shareModalProps.topLinkReachMessage as React.ReactElement),
    ).toContain("share_modal.options.top_message.inherited_edit");
  });

  it("shows the only-owner top message for the current last owner", () => {
    mockedAccesses = [
      buildAccess({
        role: Role.OWNER,
        max_role: Role.OWNER,
        user: {
          id: "owner-1",
          email: "owner@example.test",
          full_name: "Owner User",
          short_name: "OU",
          language: "en",
        },
        abilities: {
          ...buildAccess().abilities,
          set_role_to: [],
        },
      }),
    ];

    renderModal();
    const shareModalProps = capturedShareModalProps[0]!;

    expect(shareModalProps.accessRoleTopMessage(shareModalProps.accesses[0])).toBe(
      "share_modal.options.top_message.only_owner",
    );
  });

  it("keeps the copy-link footer public-vs-fallback behavior", async () => {
    mockedItem = buildItem({
      computed_link_reach: LinkReach.PUBLIC,
      type: ItemType.FOLDER,
      share_url: "https://share.example.test/item-1",
    });

    renderModal();
    await capturedCopyFooterProps[0]!.onCopyLink();
    expect(copyToClipboard).toHaveBeenCalledWith(
      "https://share.example.test/item-1",
    );
    expect(posthogCapture).not.toHaveBeenCalled();

    copyToClipboard.mockReset();
    mockedItem = buildItem({
      computed_link_reach: LinkReach.RESTRICTED,
      share_url: null,
      type: ItemType.FILE,
    });

    renderModal();
    await capturedCopyFooterProps[0]!.onCopyLink();
    expect(copyToClipboard).toHaveBeenCalledWith(
      "http://drive.example.test/explorer/items/files/item-1",
    );
    expect(posthogCapture).toHaveBeenCalledWith("click_copy_link", {
      item_id: "item-1",
      item_title: "Report.pdf",
      item_size: 123,
      item_mimetype: "application/pdf",
      item_type: ItemType.FILE,
      item_link_reach: LinkReach.RESTRICTED,
      item_link_role: LinkRole.READER,
    });
  });

  it("keeps public file copy links on the standalone file preview route", async () => {
    mockedItem = buildItem({
      computed_link_reach: LinkReach.PUBLIC,
      share_url: "https://share.example.test/file-token",
      type: ItemType.FILE,
    });

    renderModal();
    await capturedCopyFooterProps[0]!.onCopyLink();

    expect(copyToClipboard).toHaveBeenCalledWith(
      "http://drive.example.test/explorer/items/files/item-1",
    );
  });

  it("refetches public folders before falling back to direct copy links", async () => {
    mockedItem = buildItem({
      computed_link_reach: LinkReach.PUBLIC,
      share_url: null,
      type: ItemType.FOLDER,
    });
    refetchItem.mockResolvedValueOnce({
      data: buildItem({
        computed_link_reach: LinkReach.PUBLIC,
        share_url: "https://share.example.test/folder-token",
        type: ItemType.FOLDER,
      }),
    });

    renderModal();
    await capturedCopyFooterProps[0]!.onCopyLink();

    expect(refetchItem).toHaveBeenCalled();
    expect(copyToClipboard).toHaveBeenCalledWith(
      "https://share.example.test/folder-token",
    );
    expect(posthogCapture).not.toHaveBeenCalled();
  });

  it("updates link reach and role through the canonical mutation hook", () => {
    renderModal();
    const shareModalProps = capturedShareModalProps[0]!;

    shareModalProps.onUpdateLinkRole(LinkRole.EDITOR);
    shareModalProps.onUpdateLinkReach(LinkReach.PUBLIC);
    shareModalProps.onUpdateLinkReach(LinkReach.RESTRICTED);

    expect(mutateUpdateLinkConfiguration).toHaveBeenNthCalledWith(1, {
      itemId: "item-1",
      link_reach: LinkReach.RESTRICTED,
      link_role: LinkRole.EDITOR,
    });
    expect(mutateUpdateLinkConfiguration).toHaveBeenNthCalledWith(2, {
      itemId: "item-1",
      link_reach: LinkReach.PUBLIC,
      link_role: LinkRole.READER,
    });
    expect(mutateUpdateLinkConfiguration).toHaveBeenNthCalledWith(3, {
      itemId: "item-1",
      link_reach: LinkReach.RESTRICTED,
      link_role: undefined,
    });
  });
});
