import { createEmbeddedExplorerNavigationController } from "../embeddedExplorerNavigationController";

describe("embeddedExplorerNavigationController", () => {
  it("centralizes local embedded navigation side-effects for selection, search and current folder", () => {
    const clearSelection = jest.fn();
    const resetSearch = jest.fn();
    const setCurrentItemId = jest.fn();
    const controller = createEmbeddedExplorerNavigationController({
      clearSelection,
      resetSearch,
      setCurrentItemId,
    });

    controller.navigateToItem("folder-1");
    controller.navigateToBreadcrumbItem("search");
    controller.navigateToBreadcrumbItem("folder-2");

    expect(clearSelection).toHaveBeenCalledTimes(3);
    expect(resetSearch).toHaveBeenCalledTimes(3);
    expect(setCurrentItemId).toHaveBeenNthCalledWith(1, "folder-1");
    expect(setCurrentItemId).toHaveBeenNthCalledWith(2, null);
    expect(setCurrentItemId).toHaveBeenNthCalledWith(3, "folder-2");
  });
});
