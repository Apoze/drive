import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType } from "@/features/drivers/types";
import {
  openSingleItemModal,
} from "../itemModalLaunchers";
import { ItemShareModalLauncher } from "../itemShareModalLauncher";
import { MoveItemsModalLauncher } from "../moveItemsModalLauncher";

const renderedShareModalItems: string[] = [];
const renderedMoveModalProps: Array<{
  initialFolderId?: string;
  itemIds: string[];
}> = [];

jest.mock("../modals/share/ItemShareModal", () => ({
  ItemShareModal: ({ item }: { item: { id: string } }) => {
    renderedShareModalItems.push(item.id);
    return <div data-testid="item-share-modal">{item.id}</div>;
  },
}));

jest.mock("../modals/move/ExplorerMoveFolderModal", () => ({
  ExplorerMoveFolder: ({
    initialFolderId,
    itemsToMove,
  }: {
    initialFolderId?: string;
    itemsToMove: Array<{ id: string }>;
  }) => {
    renderedMoveModalProps.push({
      initialFolderId,
      itemIds: itemsToMove.map((item) => item.id),
    });
    return <div data-testid="move-items-modal">{itemsToMove.length}</div>;
  },
}));

describe("itemModalLaunchers", () => {
  beforeEach(() => {
    renderedShareModalItems.length = 0;
    renderedMoveModalProps.length = 0;
  });

  it("centralizes single-item modal opening", () => {
    const setCurrentItem = jest.fn();
    const openModal = jest.fn();
    const item = { id: "item-1", title: "Report" };

    openSingleItemModal({
      item,
      openModal,
      setCurrentItem,
    });

    expect(setCurrentItem).toHaveBeenCalledWith(item);
    expect(openModal).toHaveBeenCalled();
  });

  it("renders the standard item share modal only for readable items", () => {
    const readableItem = {
      id: "item-1",
      title: "Report",
      type: ItemType.FILE,
      abilities: {
        accesses_view: true,
      },
    } as never;
    const unreadableItem = {
      id: "item-2",
      title: "Private report",
      type: ItemType.FILE,
      abilities: {
        accesses_view: false,
      },
    } as never;

    const html = renderToStaticMarkup(
      <>
        <ItemShareModalLauncher
          isOpen={true}
          item={readableItem}
          onClose={jest.fn()}
        />
        <ItemShareModalLauncher
          isOpen={true}
          item={unreadableItem}
          onClose={jest.fn()}
        />
      </>,
    );

    expect(html).toContain("data-testid=\"item-share-modal\"");
    expect(renderedShareModalItems).toEqual(["item-1"]);
  });

  it("renders the move modal only when it has items to move", () => {
    const item = {
      id: "item-1",
      title: "Report",
      type: ItemType.FILE,
    } as never;

    const html = renderToStaticMarkup(
      <>
        <MoveItemsModalLauncher
          isOpen={true}
          itemsToMove={[item]}
          onClose={jest.fn()}
          initialFolderId="folder-1"
        />
        <MoveItemsModalLauncher
          isOpen={true}
          itemsToMove={[]}
          onClose={jest.fn()}
          initialFolderId="folder-2"
        />
      </>,
    );

    expect(html).toContain("data-testid=\"move-items-modal\"");
    expect(renderedMoveModalProps).toEqual([
      {
        initialFolderId: "folder-1",
        itemIds: ["item-1"],
      },
    ]);
  });
});
