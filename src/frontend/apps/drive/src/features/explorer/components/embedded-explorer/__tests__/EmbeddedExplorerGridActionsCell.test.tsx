import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType, ItemUploadState } from "@/features/drivers/types";
import { useDisableDragGridItem } from "../hooks";
import { useEmbeddedExplorerGirdContext } from "../EmbeddedExplorerGrid";
import {
  EmbeddedExplorerGridActionsCell,
  EmbeddedExplorerGridActionsCellProps,
} from "../EmbeddedExplorerGridActionsCell";

const renderedButtonProps: Array<{
  onClick?: () => void;
  ["aria-label"]?: string;
}> = [];
const renderedDraggableProps: Array<{
  disabled?: boolean;
  item?: unknown;
  id?: string;
}> = [];
const renderedDropdownProps: Array<{
  menuItems?: unknown;
  onModalOpenChange?: (isModalOpen: boolean) => void;
}> = [];

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, values?: Record<string, string>) =>
      values?.name ? `${key}:${values.name}` : key,
  }),
  initReactI18next: {
    type: "3rdParty",
    init: jest.fn(),
  },
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: { onClick?: () => void; ["aria-label"]?: string }) => {
    renderedButtonProps.push(props);
    return <button />;
  },
}));

jest.mock("@/features/explorer/components/Draggable", () => ({
  Draggable: (props: {
    children?: React.ReactNode;
    disabled?: boolean;
    item?: unknown;
    id?: string;
  }) => {
    renderedDraggableProps.push(props);
    return <div>{props.children}</div>;
  },
}));

jest.mock("../hooks", () => ({
  useDisableDragGridItem: jest.fn(),
}));

jest.mock("../../item-actions/ItemActionDropdown", () => ({
  ItemActionDropdown: (props: {
    trigger?: React.ReactNode;
    menuItems?: unknown;
    onModalOpenChange?: (isModalOpen: boolean) => void;
  }) => {
    renderedDropdownProps.push(props);
    return <div>{props.trigger}</div>;
  },
}));

jest.mock("../EmbeddedExplorerGrid", () => ({
  useEmbeddedExplorerGirdContext: jest.fn(),
}));

const mockedUseDisableDragGridItem = jest.mocked(useDisableDragGridItem);
const mockedUseEmbeddedExplorerGirdContext = jest.mocked(
  useEmbeddedExplorerGirdContext,
);

const buildItem = (overrides: Record<string, unknown> = {}) =>
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
      move: true,
    },
    ...overrides,
  }) as never;

describe("EmbeddedExplorerGridActionsCell", () => {
  let useStateSpy: jest.SpiedFunction<typeof React.useState> | undefined;

  beforeEach(() => {
    renderedButtonProps.length = 0;
    renderedDraggableProps.length = 0;
    renderedDropdownProps.length = 0;
    mockedUseDisableDragGridItem.mockReturnValue(false);
    mockedUseEmbeddedExplorerGirdContext.mockReturnValue({
      setIsActionModalOpen: jest.fn(),
      isActionModalOpen: false,
      getContextMenuItems: jest.fn(() => [{ label: "custom-action" }]),
    } as never);
  });

  afterEach(() => {
    useStateSpy?.mockRestore();
  });

  it("wires the draggable host, custom menu items and menu toggle", () => {
    const setIsOpen = jest.fn();
    useStateSpy = jest
      .spyOn(React, "useState")
      .mockImplementationOnce((() => [false, setIsOpen]) as never);
    const params = {
      cell: { id: "cell-1" },
      row: { original: buildItem() },
    } as unknown as EmbeddedExplorerGridActionsCellProps;

    renderToStaticMarkup(<EmbeddedExplorerGridActionsCell {...params} />);

    renderedButtonProps[0]?.onClick?.();

    expect(renderedDraggableProps[0]).toMatchObject({
      id: "cell-1",
      disabled: false,
      item: expect.objectContaining({ id: "item-1" }),
    });
    expect(renderedDropdownProps[0]).toMatchObject({
      menuItems: [{ label: "custom-action" }],
    });
    expect(renderedButtonProps[0]?.["aria-label"]).toBe(
      "explorer.grid.actions.button_aria_label:Report",
    );
    expect(setIsOpen).toHaveBeenCalledWith(true);
  });

  it("disables drag when either drag is disabled or an action modal is already open", () => {
    mockedUseDisableDragGridItem.mockReturnValue(true);
    mockedUseEmbeddedExplorerGirdContext.mockReturnValue({
      setIsActionModalOpen: jest.fn(),
      isActionModalOpen: true,
      getContextMenuItems: jest.fn(() => []),
    } as never);
    const params = {
      cell: { id: "cell-1" },
      row: { original: buildItem() },
    } as unknown as EmbeddedExplorerGridActionsCellProps;

    renderToStaticMarkup(<EmbeddedExplorerGridActionsCell {...params} />);

    expect(renderedDraggableProps[0]?.disabled).toBe(true);
  });

  it("forwards modal-open changes back to the embedded grid context", () => {
    const setIsActionModalOpen = jest.fn();
    mockedUseEmbeddedExplorerGirdContext.mockReturnValue({
      setIsActionModalOpen,
      isActionModalOpen: false,
      getContextMenuItems: jest.fn(() => []),
    } as never);
    const params = {
      cell: { id: "cell-1" },
      row: { original: buildItem() },
    } as unknown as EmbeddedExplorerGridActionsCellProps;

    renderToStaticMarkup(<EmbeddedExplorerGridActionsCell {...params} />);

    renderedDropdownProps[0]?.onModalOpenChange?.(true);

    expect(setIsActionModalOpen).toHaveBeenCalledWith(true);
  });

  it("hides the action dropdown while a regular item is duplicating", () => {
    const params = {
      cell: { id: "cell-1" },
      row: {
        original: buildItem({
          upload_state: ItemUploadState.DUPLICATING,
        }),
      },
    } as unknown as EmbeddedExplorerGridActionsCellProps;

    const html = renderToStaticMarkup(
      <EmbeddedExplorerGridActionsCell {...params} />,
    );

    expect(html).toBe("");
    expect(renderedDraggableProps).toHaveLength(0);
    expect(renderedDropdownProps).toHaveLength(0);
  });
});
