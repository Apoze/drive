import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType } from "@/features/drivers/types";
import { MenuItem } from "@gouvfr-lasuite/ui-kit";
import { useItemActionMenuItems } from "../../../hooks/useItemActionMenuItems";
import { ItemActionDropdown } from "../ItemActionDropdown";

const renderedDropdownProps: Array<{
  options?: MenuItem[];
  isOpen?: boolean;
  onOpenChange?: (isOpen: boolean) => void;
}> = [];

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  DropdownMenu: (props: {
    children?: React.ReactNode;
    options?: MenuItem[];
    isOpen?: boolean;
    onOpenChange?: (isOpen: boolean) => void;
  }) => {
    renderedDropdownProps.push(props);
    return <div>{props.children}</div>;
  },
}));

jest.mock("../../../hooks/useItemActionMenuItems", () => ({
  useItemActionMenuItems: jest.fn(),
}));

const mockedUseItemActionMenuItems = jest.mocked(useItemActionMenuItems);

const buildItem = () =>
  ({
    id: "item-1",
    title: "Report",
    filename: "Report.txt",
    creator: {
      id: "user-1",
      full_name: "Jane Doe",
      short_name: "JD",
    },
    type: ItemType.FILE,
    ancestors_link_reach: null,
    ancestors_link_role: null,
    computed_link_reach: null,
    computed_link_role: null,
    upload_state: "ready",
    updated_at: new Date("2026-03-23T00:00:00Z"),
    description: "",
    created_at: new Date("2026-03-23T00:00:00Z"),
    path: "/Report.txt",
    abilities: {
      accesses_view: true,
      move: true,
    },
  }) as never;

describe("ItemActionDropdown", () => {
  beforeEach(() => {
    renderedDropdownProps.length = 0;
  });

  it("uses the generated menu items when no custom menu is provided", () => {
    const generatedMenuItems = [
      {
        label: "generated-item",
      },
    ] as MenuItem[];
    const getMenuItems = jest.fn(() => generatedMenuItems);
    const onModalOpenChange = jest.fn();

    mockedUseItemActionMenuItems.mockReturnValue({
      getMenuItems,
      modals: <div>generated-modals</div>,
      isModalOpen: false,
    });

    const html = renderToStaticMarkup(
      <ItemActionDropdown
        item={buildItem()}
        itemId="effective-1"
        isOpen={true}
        setIsOpen={jest.fn()}
        trigger={<button>trigger</button>}
        onModalOpenChange={onModalOpenChange}
        minimal={true}
      />,
    );

    expect(mockedUseItemActionMenuItems).toHaveBeenCalledWith({
      onModalOpenChange,
    });
    expect(getMenuItems).toHaveBeenCalledWith(
      expect.objectContaining({ id: "item-1" }),
      {
        minimal: true,
        itemId: "effective-1",
      },
    );
    expect(renderedDropdownProps[0]).toMatchObject({
      options: generatedMenuItems,
      isOpen: true,
    });
    expect(html).toContain("generated-modals");
  });

  it("prefers explicit custom menu items over generated ones", () => {
    const getMenuItems = jest.fn(() => [
      {
        label: "generated-item",
      },
    ] as MenuItem[]);
    const customMenuItems = [
      {
        label: "custom-item",
      },
    ] as MenuItem[];

    mockedUseItemActionMenuItems.mockReturnValue({
      getMenuItems,
      modals: null,
      isModalOpen: false,
    });

    renderToStaticMarkup(
      <ItemActionDropdown
        item={buildItem()}
        isOpen={false}
        setIsOpen={jest.fn()}
        trigger={<button>trigger</button>}
        menuItems={customMenuItems}
      />,
    );

    expect(getMenuItems).not.toHaveBeenCalled();
    expect(renderedDropdownProps[0]).toMatchObject({
      options: customMenuItems,
      isOpen: false,
    });
  });
});
