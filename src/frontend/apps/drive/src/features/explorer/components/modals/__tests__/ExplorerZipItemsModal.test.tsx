import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { useItem } from "@/features/explorer/hooks/useQueries";
import { ExplorerZipItemsModal } from "../ExplorerZipItemsModal";

const pickFolderModalProps: Array<{
  initialFolderId?: string;
}> = [];

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@/features/api/APIError", () => ({
  errorToString: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: ({ children }: { children?: React.ReactNode }) => (
    <button>{children}</button>
  ),
  Modal: ({
    children,
  }: {
    children?: React.ReactNode;
  }) => <div>{children}</div>,
  ModalSize: {
    SMALL: "small",
  },
  useModal: jest.fn(),
}));

jest.mock("react-hook-form", () => ({
  FormProvider: ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  ),
  useForm: () => ({
    handleSubmit: (callback: (data: { archive_name: string }) => void) => () =>
      callback({ archive_name: "archive.zip" }),
    reset: jest.fn(),
  }),
}));

jest.mock("@/features/explorer/api/useArchiveZip", () => ({
  useStartArchiveZip: () => ({
    isPending: false,
    mutateAsync: jest.fn(),
  }),
}));

jest.mock("@/features/explorer/components/toasts/ArchiveJobToast", () => ({
  showArchiveJobToast: jest.fn(),
}));

jest.mock("@/features/explorer/hooks/useQueries", () => ({
  useItem: jest.fn(),
}));

jest.mock("@/features/forms/components/RhfInput", () => ({
  RhfInput: () => <div>rhf-input</div>,
}));

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  addToast: jest.fn(),
  ToasterItem: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock("./../ExplorerPickFolderModal", () => ({
  ExplorerPickFolderModal: (props: { initialFolderId?: string }) => {
    pickFolderModalProps.push(props);
    return <div>pick-folder-modal</div>;
  },
}));

const mockedUseModal = jest.mocked(useModal);
const mockedUseItem = jest.mocked(useItem);

describe("ExplorerZipItemsModal", () => {
  beforeEach(() => {
    pickFolderModalProps.length = 0;
    mockedUseModal.mockReturnValue({
      close: jest.fn(),
      isOpen: true,
      open: jest.fn(),
    } as never);
    mockedUseItem.mockReturnValue({
      data: {
        title: "Destination",
      },
    } as never);
  });

  it("passes the current destination folder through to the shared pick-folder modal", () => {
    renderToStaticMarkup(
      <ExplorerZipItemsModal
        isOpen={true}
        onClose={jest.fn()}
        initialDestinationFolderId="folder-zip"
        items={[
          {
            id: "item-1",
            title: "Report",
            filename: "Report.txt",
            type: "file",
          } as never,
        ]}
      />,
    );

    expect(pickFolderModalProps[0]).toMatchObject({
      initialFolderId: "folder-zip",
    });
  });
});
