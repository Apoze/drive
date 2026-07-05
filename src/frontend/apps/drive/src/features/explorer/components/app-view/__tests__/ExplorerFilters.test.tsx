import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  ExplorerFilters,
  ExplorerFilterScope,
  ExplorerFilterType,
  ExplorerFilterWorkspace,
} from "../ExplorerFilters";
import { useAppExplorer } from "../AppExplorer";
import { useItems } from "../../../hooks/useQueries";

const renderedFilterProps: Array<{
  label?: string;
  options?: Array<{ value?: string; label?: string }>;
  selectedKey?: string | null;
  onSelectionChange?: (value: string | null) => void;
  isDisabled?: boolean;
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
  Filter: (props: {
    label?: string;
    options?: Array<{ value?: string; label?: string }>;
    selectedKey?: string | null;
    onSelectionChange?: (value: string | null) => void;
    isDisabled?: boolean;
  }) => {
    renderedFilterProps.push(props);
    return <div>{props.label}</div>;
  },
  IconSize: {
    SMALL: "small",
  },
}));

jest.mock("../AppExplorer", () => ({
  useAppExplorer: jest.fn(),
}));

jest.mock("../../../hooks/useQueries", () => ({
  useItems: jest.fn(),
}));

jest.mock("../../icons/ItemIcon", () => ({
  ItemIcon: () => <div>item-icon</div>,
}));

const mockedUseAppExplorer = jest.mocked(useAppExplorer);
const mockedUseItems = jest.mocked(useItems);

describe("ExplorerFilters", () => {
  beforeEach(() => {
    renderedFilterProps.length = 0;
    mockedUseAppExplorer.mockReturnValue({
      filters: {},
      onFiltersChange: jest.fn(),
    } as never);
    mockedUseItems.mockReturnValue({
      data: [
        {
          id: "workspace-1",
          title: "Workspace",
        },
      ],
    } as never);
  });

  it("routes filter changes through the canonical ExplorerFilters host", () => {
    const onFiltersChange = jest.fn();
    mockedUseAppExplorer.mockReturnValue({
      filters: {
        type: "file",
      },
      onFiltersChange,
    } as never);

    renderToStaticMarkup(<ExplorerFilters />);

    renderedFilterProps[0]?.onSelectionChange?.("folder");
    renderedFilterProps[0]?.onSelectionChange?.("all");

    expect(renderedFilterProps[0]).toMatchObject({
      label: "explorer.filters.type.label",
      selectedKey: "file",
    });
    expect(onFiltersChange).toHaveBeenNthCalledWith(1, {
      type: "folder",
    });
    expect(onFiltersChange).toHaveBeenNthCalledWith(2, {});
  });

  it("keeps the type, workspace and scope filter options stable", () => {
    renderToStaticMarkup(
      <>
        <ExplorerFilterType value={null} onChange={jest.fn()} />
        <ExplorerFilterWorkspace
          value={null}
          onChange={jest.fn()}
          isDisabled={true}
        />
        <ExplorerFilterScope value={null} onChange={jest.fn()} />
      </>,
    );

    expect(renderedFilterProps[0]?.options).toHaveLength(3);
    expect(renderedFilterProps[1]).toMatchObject({
      label: "explorer.filters.folders.label",
      isDisabled: true,
    });
    expect(renderedFilterProps[1]?.options).toHaveLength(2);
    expect(renderedFilterProps[2]).toMatchObject({
      label: "explorer.filters.scopes.label",
    });
    expect(renderedFilterProps[2]?.options).toHaveLength(2);
  });
});
