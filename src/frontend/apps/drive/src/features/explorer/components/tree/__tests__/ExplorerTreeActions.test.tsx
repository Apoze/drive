import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ExplorerTreeActions } from "../ExplorerTreeActions";
import { useGlobalExplorer } from "../../GlobalExplorerContext";
import { useCreateMenuItems } from "../../../hooks/useCreateMenuItems";

const renderedSearchProps: Array<{
  keyboardShortcut?: boolean;
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

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  DropdownMenu: ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  ),
  useDropdownMenu: () => ({
    isOpen: false,
    setIsOpen: jest.fn(),
  }),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: ({ children }: { children?: React.ReactNode }) => (
    <button>{children}</button>
  ),
}));

jest.mock("../../app-view/ExplorerSearchButton", () => ({
  ExplorerSearchButton: (props: { keyboardShortcut?: boolean }) => {
    renderedSearchProps.push(props);
    return <div>search-button</div>;
  },
}));

jest.mock("../../GlobalExplorerContext", () => ({
  useGlobalExplorer: jest.fn(),
}));

jest.mock("../../../hooks/useCreateMenuItems", () => ({
  useCreateMenuItems: jest.fn(),
}));

const mockedUseGlobalExplorer = jest.mocked(useGlobalExplorer);
const mockedUseCreateMenuItems = jest.mocked(useCreateMenuItems);

describe("ExplorerTreeActions", () => {
  beforeEach(() => {
    renderedSearchProps.length = 0;
    mockedUseCreateMenuItems.mockReturnValue({
      menuItems: [],
      modals: <div>modals</div>,
    } as never);
  });

  it("stays hidden until the tree is initialized", () => {
    mockedUseGlobalExplorer.mockReturnValue({
      treeIsInitialized: false,
    } as never);

    const html = renderToStaticMarkup(<ExplorerTreeActions />);

    expect(html).toBe("");
    expect(renderedSearchProps).toEqual([]);
  });

  it("wires the canonical search launcher with keyboard shortcut support", () => {
    mockedUseGlobalExplorer.mockReturnValue({
      treeIsInitialized: true,
    } as never);

    const html = renderToStaticMarkup(<ExplorerTreeActions />);

    expect(html).toContain("explorer.tree.createFolder");
    expect(html).toContain("modals");
    expect(renderedSearchProps).toEqual([
      {
        keyboardShortcut: true,
      },
    ]);
  });
});
