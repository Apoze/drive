import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType } from "@/features/drivers/types";
import { useGlobalExplorer } from "../../GlobalExplorerContext";
import { useAppExplorer } from "../AppExplorer";
import { AppExplorerGrid } from "../AppExplorerGrid";
import { openWopiInNewTab } from "@/features/ui/preview/wopi/openWopi";

const mockModalOpen = jest.fn();
const mockModalClose = jest.fn();

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

jest.mock("@gouvfr-lasuite/cunningham-react", () => {
  const actual = jest.requireActual("@gouvfr-lasuite/cunningham-react");

  return {
    ...actual,
    Loader: () => <div>loader</div>,
    useModal: () => ({
      isOpen: false,
      open: mockModalOpen,
      onClose: mockModalClose,
    }),
    useCunningham: () => ({
      t: (key: string) => key,
    }),
  };
});

jest.mock("@/features/ui/preview/wopi/openWopi", () => ({
  openWopiInNewTab: jest.fn(),
}));

jest.mock("../../modals/ConvertLegacyFileModal", () => ({
  ConvertLegacyFileModal: () => <div>convert-modal</div>,
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
const mockedOpenWopiInNewTab = jest.mocked(openWopiInNewTab);

describe("AppExplorerGrid", () => {
  beforeEach(() => {
    embeddedExplorerGridProps.length = 0;
    mockModalOpen.mockClear();
    mockModalClose.mockClear();
    mockedOpenWopiInNewTab.mockClear();
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

  it("opens the conversion modal before WOPI when conversion is available", () => {
    const fileItem = {
      id: "item-1",
      title: "Report",
      type: ItemType.FILE,
      url: "http://example.test/file",
      is_wopi_supported: true,
      abilities: {
        convert: true,
      },
    } as never;

    mockedUseAppExplorer.mockReturnValue({
      childrenItems: [fileItem],
      disableItemDragAndDrop: false,
    } as never);

    renderToStaticMarkup(<AppExplorerGrid />);

    embeddedExplorerGridProps[0]?.onFileClick?.(fileItem);

    expect(mockModalOpen).toHaveBeenCalledTimes(1);
    expect(mockedOpenWopiInNewTab).not.toHaveBeenCalled();
  });

  it("keeps WOPI opening as the default when conversion is not available", () => {
    const fileItem = {
      id: "item-1",
      title: "Report",
      type: ItemType.FILE,
      is_wopi_supported: true,
      abilities: {
        convert: false,
      },
    } as never;

    mockedUseAppExplorer.mockReturnValue({
      childrenItems: [fileItem],
      disableItemDragAndDrop: false,
    } as never);

    renderToStaticMarkup(<AppExplorerGrid />);

    embeddedExplorerGridProps[0]?.onFileClick?.(fileItem);

    expect(mockedOpenWopiInNewTab).toHaveBeenCalledWith("item-1");
    expect(mockModalOpen).not.toHaveBeenCalled();
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
