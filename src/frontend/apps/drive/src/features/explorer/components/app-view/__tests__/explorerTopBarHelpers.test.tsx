import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType, type Item } from "@/features/drivers/types";
import { DefaultRoute } from "@/utils/defaultRoutes";
import {
  ALL_FILTER_VALUE,
  buildExplorerScopeFilterOptions,
  buildExplorerTypeFilterOptions,
  buildExplorerWorkspaceFilterOptions,
  getMobileBreadcrumbState,
  handleFilterChange,
  resolveMobileBreadcrumbBackTarget,
  shouldShowAppBreadcrumbActions,
} from "../explorerTopBarHelpers";

const buildItem = (overrides: Partial<Item> = {}): Item =>
  ({
    id: "item-1",
    title: "Folder",
    filename: "Folder",
    creator: {
      id: "user-1",
      full_name: "Jane Doe",
      short_name: "JD",
    },
    type: ItemType.FOLDER,
    ancestors_link_reach: null,
    ancestors_link_role: null,
    computed_link_reach: null,
    computed_link_role: null,
    upload_state: "ready",
    updated_at: new Date("2026-03-22T00:00:00Z"),
    description: "",
    created_at: new Date("2026-03-22T00:00:00Z"),
    path: "/Folder",
    abilities: {
      children_create: true,
    } as never,
    ...overrides,
  }) as Item;

describe("explorerTopBarHelpers", () => {
  const t = (key: string) => key;

  it("keeps breadcrumb actions visibility scoped to my-files or writable folders", () => {
    expect(
      shouldShowAppBreadcrumbActions({
        pathname: "/explorer/items/my-files",
      }),
    ).toBe(true);
    expect(
      shouldShowAppBreadcrumbActions({
        pathname: "/explorer/items/favorites",
      }),
    ).toBe(false);
    expect(
      shouldShowAppBreadcrumbActions({
        pathname: "/explorer/items/123",
        item: buildItem({
          abilities: {
            children_create: true,
          } as never,
        }),
      }),
    ).toBe(true);
  });

  it("resolves mobile breadcrumb state and back targets consistently", () => {
    const state = getMobileBreadcrumbState([
      {
        id: "workspace-1",
        title: "Workspace",
        path: "",
        depth: 0,
        main_workspace: false,
      },
      {
        id: "folder-1",
        title: "Folder",
        path: "",
        depth: 1,
        main_workspace: false,
      },
    ]);

    expect(state).toMatchObject({
      workspace: {
        id: "workspace-1",
      },
      current: {
        id: "folder-1",
      },
      parent: {
        id: "workspace-1",
      },
      isRoot: false,
    });
    expect(resolveMobileBreadcrumbBackTarget(DefaultRoute.MY_FILES)).toBe(
      "/explorer/items/my-files",
    );
    expect(resolveMobileBreadcrumbBackTarget("folder-1")).toBeUndefined();
  });

  it("builds filter options and reset semantics without changing product labels", () => {
    expect(
      handleFilterChange(
        {
          type: ItemType.FILE,
        },
        "type",
        ALL_FILTER_VALUE,
      ),
    ).toEqual({});
    expect(handleFilterChange({}, "scope", "deleted")).toEqual({
      scope: "deleted",
    });

    const typeOptions = buildExplorerTypeFilterOptions(t as never);
    const scopeOptions = buildExplorerScopeFilterOptions(t as never);
    const workspaceOptions = buildExplorerWorkspaceFilterOptions({
      items: [buildItem({ id: "workspace-1", title: "Workspace" })],
      t: t as never,
      renderIcon: () => <div>icon</div>,
    });

    expect(typeOptions).toHaveLength(3);
    expect(scopeOptions).toHaveLength(2);
    expect(workspaceOptions).toHaveLength(2);
    expect(renderToStaticMarkup(typeOptions[0].render?.() as never)).toContain(
      "explorer.filters.type.options.folder",
    );
    expect(
      renderToStaticMarkup(workspaceOptions[0].render?.() as never),
    ).toContain("Workspace");
  });
});
