import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  ExplorerCreateFileModal,
  ExplorerCreateFileType,
} from "../ExplorerCreateFileModal";
import {
  SelectionStore,
  SelectionStoreContext,
} from "@/features/explorer/stores/selectionStore";

const renderedButtons: Array<{
  disabled?: boolean;
  children?: React.ReactNode;
}> = [];
const renderedModalProps: Array<{
  title?: string;
}> = [];

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
    push: jest.fn(),
  }),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: { disabled?: boolean; children?: React.ReactNode }) => {
    renderedButtons.push(props);
    return <button>{props.children}</button>;
  },
  Modal: ({
    title,
    children,
    rightActions,
  }: {
    title?: string;
    children?: React.ReactNode;
    rightActions?: React.ReactNode;
  }) => {
    renderedModalProps.push({ title });
    return (
      <div>
        {title}
        {rightActions}
        {children}
      </div>
    );
  },
  ModalSize: {
    MEDIUM: "medium",
  },
}));

jest.mock("../../../hooks/useMutations", () => ({
  useMutationCreateNewFile: () => ({
    isPending: false,
    mutate: jest.fn(),
  }),
}));

jest.mock("../../GlobalExplorerContext", () => ({
  useGlobalExplorer: () => ({
    openSinglePreview: jest.fn(),
  }),
}));

const renderWithSelectionStore = (element: React.ReactElement) =>
  renderToStaticMarkup(
    <SelectionStoreContext.Provider value={new SelectionStore()}>
      {element}
    </SelectionStoreContext.Provider>,
  );

describe("ExplorerCreateFileModal", () => {
  beforeEach(() => {
    renderedButtons.length = 0;
    renderedModalProps.length = 0;
  });

  it("keeps quick-create mounted on the canonical modal host with its specific title", () => {
    const html = renderWithSelectionStore(
      <ExplorerCreateFileModal
        isOpen={true}
        onClose={jest.fn()}
        type={ExplorerCreateFileType.DOC}
      />,
    );

    expect(renderedModalProps[0]).toEqual({
      title: "explorer.actions.createFile.modal.title_doc",
    });
    expect(html).not.toContain("explorer.actions.createFile.modal.kind_label");
    expect(renderedButtons[1]?.disabled).toBe(true);
  });

  it("keeps the advanced create-file picker available from the same modal", () => {
    const html = renderWithSelectionStore(
      <ExplorerCreateFileModal isOpen={true} onClose={jest.fn()} />,
    );

    expect(renderedModalProps[0]).toEqual({
      title: "explorer.actions.createFile.modal.title",
    });
    expect(html).toContain("explorer.actions.createFile.modal.kind_label");
    expect(html).toContain("explorer.actions.createFile.modal.extension_label");
    expect(renderedButtons[1]?.disabled).toBe(true);
  });
});
