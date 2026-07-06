import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import SdkExplorerPage from "@/pages/sdk/explorer";
import { SelectionStore } from "@/features/explorer/stores/selectionStore";

const mockedUseEmbeddedExplorer = jest.fn();

jest.mock("@/features/explorer/components/embedded-explorer/EmbeddedExplorer", () => ({
  EmbeddedExplorer: (props: Record<string, unknown>) => <div>embedded-explorer:{String(props.displayMode)}</div>,
  useEmbeddedExplorer: (...args: unknown[]) => mockedUseEmbeddedExplorer(...args),
}));

jest.mock(
  "@/features/explorer/components/embedded-explorer/EmbeddedExplorerGridNameCell",
  () => ({
    EmbeddedExplorerGridNameCell: () => <div>name-cell</div>,
  }),
);

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Tooltip: ({ children }: { children?: React.ReactNode }) => (
    <div>tooltip{children}</div>
  ),
}));

jest.mock("@/features/layouts/components/sdk/SdkLayout", () => ({
  getSdkPickerLayout: (page: React.ReactElement) => <div>sdk-layout{page}</div>,
  useSdkContext: () => ({
    token: "sdk-token",
  }),
}));

jest.mock("@/features/sdk/SdkPickerFooter", () => ({
  PickerFooter: ({ token, selectedItems }: { token: string; selectedItems: unknown[] }) => (
    <div>picker-footer:{token}:{selectedItems.length}</div>
  ),
}));

describe("SdkExplorerPage", () => {
  it("wires EmbeddedExplorer and PickerFooter with the SDK token", () => {
    const selectionStore = new SelectionStore();
    selectionStore.setSelectedItems([{ id: "item-1" }] as never);
    mockedUseEmbeddedExplorer.mockReturnValue({
      displayMode: "sdk",
      selectionStore,
    });

    const html = renderToStaticMarkup(<SdkExplorerPage />);

    expect(html).toContain("embedded-explorer:sdk");
    expect(html).toContain("picker-footer:sdk-token:1");
    expect(mockedUseEmbeddedExplorer).toHaveBeenCalledWith(
      expect.objectContaining({
        gridProps: expect.objectContaining({
          canSelect: expect.any(Function),
          disableItemDragAndDrop: true,
          displayMode: "sdk",
          enableMetaKeySelection: true,
        }),
        isCompact: true,
      }),
    );
  });
});
