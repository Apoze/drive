import { createSelectionController } from "../selectionController";

describe("selectionController", () => {
  it("centralizes clear, replace and single-item selection operations", () => {
    const setSelectedItems = jest.fn();
    const itemA = { id: "item-a", title: "A" };
    const itemB = { id: "item-b", title: "B" };
    const controller = createSelectionController({
      setSelectedItems,
    });

    controller.selectSingleItem(itemA);
    controller.replaceSelection([itemA, itemB]);
    controller.clearSelection();

    expect(setSelectedItems).toHaveBeenNthCalledWith(1, [itemA]);
    expect(setSelectedItems).toHaveBeenNthCalledWith(2, [itemA, itemB]);
    expect(setSelectedItems).toHaveBeenNthCalledWith(3, []);
  });
});
