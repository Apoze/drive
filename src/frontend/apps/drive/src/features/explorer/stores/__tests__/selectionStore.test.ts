import { SelectionStore } from "../selectionStore";
import type { Item } from "@/features/drivers/types";

const buildItem = (id: string): Item => ({ id, title: id }) as Item;

describe("SelectionStore", () => {
  it("notifies only changed id listeners and global subscribers", () => {
    const store = new SelectionStore();
    const itemA = buildItem("a");
    const itemB = buildItem("b");
    const itemC = buildItem("c");
    const onA = jest.fn();
    const onB = jest.fn();
    const onC = jest.fn();
    const onGlobal = jest.fn();

    store.subscribeToId("a", onA);
    store.subscribeToId("b", onB);
    store.subscribeToId("c", onC);
    store.subscribe(onGlobal);

    store.setSelectedItems([itemA, itemB]);

    expect(onA).toHaveBeenCalledTimes(1);
    expect(onB).toHaveBeenCalledTimes(1);
    expect(onC).not.toHaveBeenCalled();
    expect(onGlobal).toHaveBeenCalledTimes(1);

    store.setSelectedItems([itemA, itemB]);

    expect(onA).toHaveBeenCalledTimes(1);
    expect(onB).toHaveBeenCalledTimes(1);
    expect(onC).not.toHaveBeenCalled();
    expect(onGlobal).toHaveBeenCalledTimes(1);

    store.setSelectedItems([itemB, itemC]);

    expect(onA).toHaveBeenCalledTimes(2);
    expect(onB).toHaveBeenCalledTimes(1);
    expect(onC).toHaveBeenCalledTimes(1);
    expect(onGlobal).toHaveBeenCalledTimes(2);
  });

  it("supports updater functions and map snapshots", () => {
    const store = new SelectionStore();
    const itemA = buildItem("a");
    const itemB = buildItem("b");

    store.setSelectedItems([itemA]);
    store.setSelectedItems((items) => [...items, itemB]);

    expect(store.getSelectedItems()).toEqual([itemA, itemB]);
    expect(store.getSelectedItemsMap()).toEqual({
      a: itemA,
      b: itemB,
    });
    expect(store.isSelected("a")).toBe(true);
    expect(store.isSelected("c")).toBe(false);
  });
});
