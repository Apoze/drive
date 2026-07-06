import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType } from "@/features/drivers/types";
import { useGlobalExplorer } from "../../GlobalExplorerContext";
import { useAppExplorer } from "../AppExplorer";
import { AppExplorerGrid } from "../AppExplorerGrid";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("next/router", () => ({
  useRouter: () => ({
    pathname: "/explorer/items/my-files",
  }),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Loader: () => <div>loader</div>,
  useCunningham: () => ({
    t: (key: string) => key,
  }),
}));

const embeddedExplorerGridProps: Array<{
  onFileClick?: (item: unknown) => void;
  clearRightPanelItem?: () => void;
}> = [];

jest.mock("../../embedded-explorer/EmbeddedExplorerGrid", () => ({
  EmbeddedExplorerGrid: (props: { onFileClick?: (item: unknown) => void }) => {
    embeddedExplorerGridProps.push(props);
    return <div>embedded-grid</div>;
  },
}));

jest.mock("../AppExplorer", () => ({
  useAppExplorer: jest.fn(),
}));

jest.mock("../../GlobalExplorerContext", () => ({
  useGlobalExplorer: jest.fn(),
}));

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  addToast: jest.fn(),
  ToasterItem: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock("@/features/ui/components/infinite-scroll/InfiniteScroll", () => ({
  InfiniteScroll: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

const mockedUseGlobalExplorer = jest.mocked(useGlobalExplorer);
const mockedUseAppExplorer = jest.mocked(useAppExplorer);

describe("AppExplorerGrid", () => {
  beforeEach(() => {
    embeddedExplorerGridProps.length = 0;
    mockedUseAppExplorer.mockReturnValue({
      childrenItems: [],
      disableItemDragAndDrop: false,
    } as never);
    mockedUseGlobalExplorer.mockReturnValue({
      setSelectedItems: jest.fn(),
      selectedItems: [],
      onNavigate: jest.fn(),
      clearRightPanelItem: jest.fn(),
      item: undefined,
      displayMode: "app",
      openPreview: jest.fn(),
    } as never);
  });

  it("opens item preview through the explicit preview API", () => {
    const openPreview = jest.fn();
    mockedUseGlobalExplorer.mockReturnValue({
      setSelectedItems: jest.fn(),
      selectedItems: [],
      onNavigate: jest.fn(),
      clearRightPanelItem: jest.fn(),
      item: undefined,
      displayMode: "app",
      openPreview,
    } as never);
    const fileItem = {
      id: "item-1",
      title: "Report",
      type: ItemType.FILE,
      url: "http://example.test/file",
    } as never;
    const siblingItem = {
      id: "item-2",
      title: "Notes",
      type: ItemType.FILE,
      url: "http://example.test/notes",
    } as never;

    mockedUseAppExplorer.mockReturnValue({
      childrenItems: [fileItem, siblingItem],
      disableItemDragAndDrop: false,
    } as never);

    renderToStaticMarkup(<AppExplorerGrid />);

    embeddedExplorerGridProps[0]?.onFileClick?.(fileItem);

    expect(openPreview).toHaveBeenCalledWith(fileItem, [fileItem, siblingItem]);
  });

  it("passes the explicit clear-right-panel intent down to the embedded grid", () => {
    const clearRightPanelItem = jest.fn();

    mockedUseGlobalExplorer.mockReturnValue({
      setSelectedItems: jest.fn(),
      selectedItems: [],
      onNavigate: jest.fn(),
      clearRightPanelItem,
      item: undefined,
      displayMode: "app",
      openPreview: jest.fn(),
    } as never);

    mockedUseAppExplorer.mockReturnValue({
      childrenItems: [
        {
          id: "item-1",
          title: "Report",
          type: ItemType.FILE,
          url: "http://example.test/file",
        } as never,
      ],
      disableItemDragAndDrop: false,
    } as never);

    renderToStaticMarkup(<AppExplorerGrid />);

    expect(embeddedExplorerGridProps[0]?.clearRightPanelItem).toBe(
      clearRightPanelItem,
    );
  });
});
