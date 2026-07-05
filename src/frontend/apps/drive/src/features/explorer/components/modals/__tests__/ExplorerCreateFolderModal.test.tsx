import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ExplorerCreateFolderModal } from "../ExplorerCreateFolderModal";

const mockRouterPush = jest.fn();
const mockCreateFolderMutate = jest.fn();
const mockFormReset = jest.fn();
let submitCreateFolderForm:
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

jest.mock("next/router", () => ({
  useRouter: () => ({
    push: mockRouterPush,
  }),
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
  useForm: () => ({
    handleSubmit: (callback: (data: { title: string }) => Promise<void> | void) => {
      submitCreateFolderForm = callback;
      return jest.fn();
    },
    register: () => ({
      name: "title",
      ref: jest.fn(),
    }),
    reset: mockFormReset,
  }),
}));

jest.mock("@/features/forms/components/RhfInput", () => ({
  RhfInput: () => <div>rhf-input</div>,
}));

jest.mock("../../../hooks/useMutations", () => ({
  useMutationCreateFolder: () => ({
    mutate: mockCreateFolderMutate,
  }),
}));

describe("ExplorerCreateFolderModal", () => {
  beforeEach(() => {
    submitCreateFolderForm = undefined;
    mockRouterPush.mockReset();
    mockCreateFolderMutate.mockReset();
    mockFormReset.mockReset();
  });

  it("submits the folder payload and closes without redirect inside a folder", async () => {
    renderToStaticMarkup(
      <ExplorerCreateFolderModal
        isOpen={true}
        onClose={jest.fn()}
        parentId="folder-1"
      />,
    );

    await submitCreateFolderForm?.({
      title: "Invoices",
    });

    expect(mockCreateFolderMutate).toHaveBeenCalledWith(
      {
        title: "Invoices",
        parentId: "folder-1",
      },
      expect.objectContaining({
        onSuccess: expect.any(Function),
      }),
    );
    expect(mockFormReset).toHaveBeenCalledTimes(1);
    expect(mockRouterPush).not.toHaveBeenCalled();
  });

  it("redirects to my-files when creating from the root scope", async () => {
    const onClose = jest.fn();

    renderToStaticMarkup(
      <ExplorerCreateFolderModal isOpen={true} onClose={onClose} />,
    );

    await submitCreateFolderForm?.({
      title: "Invoices",
    });
    mockCreateFolderMutate.mock.calls[0][1].onSuccess();

    expect(mockFormReset).toHaveBeenCalledTimes(2);
    expect(onClose).toHaveBeenCalled();
    expect(mockRouterPush).toHaveBeenCalledWith("/explorer/items/my-files");
  });
});
