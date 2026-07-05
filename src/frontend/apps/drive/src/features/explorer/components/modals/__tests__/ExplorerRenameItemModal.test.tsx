import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType, type Item } from "@/features/drivers/types";
import { ExplorerRenameItemModal } from "../ExplorerRenameItemModal";
import { useGlobalExplorer } from "../../GlobalExplorerContext";
import { useTreeUtils } from "../../../hooks/useTreeUtils";

const mockMutateAsync = jest.fn();
const mockReplaceRightPanelItem = jest.fn();
const mockUpdateNodeByOriginalId = jest.fn();
let capturedUseFormConfig:
  | {
      defaultValues?: {
        title?: string;
      };
    }
  | undefined;
let submitRenameForm:
  | ((data: { title: string }) => Promise<void> | void)
  | undefined;

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: {
    type: "3rdParty",
    init: jest.fn(),
  },
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: ({ children }: { children?: React.ReactNode }) => (
    <button>{children}</button>
  ),
  Modal: ({
    children,
    rightActions,
  }: {
    children?: React.ReactNode;
    rightActions?: React.ReactNode;
  }) => (
    <div>
      {rightActions}
      {children}
    </div>
  ),
  ModalSize: {
    SMALL: "small",
  },
}));

jest.mock("react-hook-form", () => ({
  FormProvider: ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  ),
  useForm: (config?: {
    defaultValues?: {
      title?: string;
    };
  }) => {
    capturedUseFormConfig = config;

    return {
      handleSubmit: (callback: (data: { title: string }) => Promise<void> | void) => {
        submitRenameForm = callback;
        return jest.fn();
      },
      register: () => ({
        name: "title",
        ref: jest.fn(),
      }),
    };
  },
}));

jest.mock("@/features/forms/components/RhfInput", () => ({
  RhfInput: () => <div>rhf-input</div>,
}));

jest.mock("../../../hooks/useMutations", () => ({
  useMutationRenameItem: () => ({
    mutateAsync: mockMutateAsync,
  }),
}));

jest.mock("../../GlobalExplorerContext", () => ({
  useGlobalExplorer: jest.fn(),
}));

jest.mock("../../../hooks/useTreeUtils", () => ({
  useTreeUtils: jest.fn(),
}));

const mockedUseGlobalExplorer = jest.mocked(useGlobalExplorer);
const mockedUseTreeUtils = jest.mocked(useTreeUtils);

const buildItem = (overrides: Partial<Item> = {}): Item => ({
  id: "item-1",
  title: "Report.txt",
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
  upload_state: "ready",
  updated_at: new Date("2026-03-22T00:00:00Z"),
  description: "",
  created_at: new Date("2026-03-22T00:00:00Z"),
  path: "/Report.txt",
  mimetype: "text/plain",
  abilities: {
    accesses_manage: false,
    accesses_view: true,
    children_create: false,
    children_list: false,
    destroy: true,
    favorite: false,
    invite_owner: false,
    link_configuration: false,
    media_auth: false,
    move: true,
    link_select_options: {
      restricted: null,
      authenticated: null,
      public: null,
    },
    partial_update: true,
    restore: false,
    retrieve: true,
    tree: false,
    update: true,
    upload_ended: false,
  },
  ...overrides,
});

describe("ExplorerRenameItemModal", () => {
  beforeEach(() => {
    capturedUseFormConfig = undefined;
    submitRenameForm = undefined;
    mockMutateAsync.mockReset();
    mockReplaceRightPanelItem.mockReset();
    mockUpdateNodeByOriginalId.mockReset();

    mockedUseGlobalExplorer.mockReturnValue({
      selectedItems: [
        buildItem({
          id: "item-1",
          title: "Panel title.txt",
          filename: "Panel title.txt",
          path: "/Panel title.txt",
        }),
      ],
      rightPanelForcedItem: undefined,
      replaceRightPanelItem: mockReplaceRightPanelItem,
    } as never);
    mockedUseTreeUtils.mockReturnValue({
      updateNodeByOriginalId: mockUpdateNodeByOriginalId,
    } as never);
    mockMutateAsync.mockImplementation(
      async (
        variables: { id: string; title: string },
        options?: {
          onSuccess?: (data: unknown, variables: { id: string; title: string }) => void;
        },
      ) => {
        options?.onSuccess?.(undefined, variables);
      },
    );
  });

  it("starts from the extensionless display title for file items", () => {
    renderToStaticMarkup(
      <ExplorerRenameItemModal
        isOpen={true}
        onClose={jest.fn()}
        item={buildItem()}
      />,
    );

    expect(capturedUseFormConfig).toEqual({
      defaultValues: {
        title: "Report",
      },
    });
  });

  it("submits the normalized rename payload and keeps tree/right-panel sync", async () => {
    const onClose = jest.fn();

    renderToStaticMarkup(
      <ExplorerRenameItemModal
        isOpen={true}
        onClose={onClose}
        item={buildItem()}
      />,
    );

    await submitRenameForm?.({
      title: "Quarterly plan",
    });

    expect(mockMutateAsync).toHaveBeenCalledWith(
      {
        title: "Quarterly plan.txt",
        id: "item-1",
      },
      expect.objectContaining({
        onSuccess: expect.any(Function),
      }),
    );
    expect(mockUpdateNodeByOriginalId).toHaveBeenCalledWith("item-1", {
      title: "Quarterly plan.txt",
    });
    expect(onClose).toHaveBeenCalled();
    expect(mockReplaceRightPanelItem).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "item-1",
        title: "Quarterly plan.txt",
        path: "/Panel title.txt",
      }),
    );
  });
});
