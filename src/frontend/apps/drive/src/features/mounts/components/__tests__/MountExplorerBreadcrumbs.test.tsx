import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useRouter } from "next/router";
import { MountExplorerBreadcrumbs, MountExplorerPrimaryAction } from "../MountExplorerBreadcrumbs";

const capturedBreadcrumbsItems: Array<Array<{ content: React.ReactNode }>> = [];
const renderedButtons: Array<Record<string, unknown>> = [];
const breadcrumbItemButtonCalls: Array<Record<string, unknown>> = [];

jest.mock("next/router", () => ({
  useRouter: jest.fn(),
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: {
    children?: React.ReactNode;
    onClick?: () => void;
    disabled?: boolean;
  }) => {
    renderedButtons.push(props as Record<string, unknown>);
    return <button>{props.children}</button>;
  },
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  HorizontalSeparator: () => <div>separator</div>,
  IconSize: {
    MEDIUM: "medium",
  },
}));

jest.mock("@/features/ui/components/icon/MountsIcon", () => ({
  MountsIcon: () => <div>mounts-icon</div>,
}));

jest.mock("@/features/ui/components/breadcrumbs/Breadcrumbs", () => ({
  Breadcrumbs: ({
    items,
  }: {
    items: Array<{ content: React.ReactNode }>;
  }) => {
    capturedBreadcrumbsItems.push(items);
    return (
      <div>
        {items.map((item, index) => (
          <div key={index}>{item.content}</div>
        ))}
      </div>
    );
  },
}));

jest.mock(
  "@/features/explorer/components/embedded-explorer/EmbeddedExplorerGridBreadcrumbs",
  () => ({
    BreadcrumbItemButton: (props: {
      item: { id: string; title: string; path: string };
      isActive?: boolean;
      onClick?: () => void;
    }) => {
      breadcrumbItemButtonCalls.push(props as Record<string, unknown>);
      return (
        <div data-path={props.item.path} data-active={String(Boolean(props.isActive))}>
          {props.item.title}
        </div>
      );
    },
  }),
);

const mockedUseRouter = jest.mocked(useRouter);

describe("MountExplorerBreadcrumbs", () => {
  beforeEach(() => {
    capturedBreadcrumbsItems.length = 0;
    renderedButtons.length = 0;
    breadcrumbItemButtonCalls.length = 0;
    mockedUseRouter.mockReturnValue({
      push: jest.fn(),
    } as never);
  });

  it("keeps the default mounts route when no mount is active", () => {
    const push = jest.fn();
    mockedUseRouter.mockReturnValue({ push } as never);

    const html = renderToStaticMarkup(<MountExplorerBreadcrumbs />);

    expect(html).toContain("mounts-icon");
    expect(html).toContain("explorer.tree.mounts");
    expect(capturedBreadcrumbsItems[0]).toHaveLength(1);

    const defaultRoute = capturedBreadcrumbsItems[0]?.[0]?.content as React.ReactElement<{
      onClick?: () => void;
    }>;
    defaultRoute.props.onClick?.();

    expect(push).toHaveBeenCalledWith("/explorer/mounts");
  });

  it("keeps root mount, path segments and actions on the canonical breadcrumbs host", () => {
    const onNavigateToPath = jest.fn();

    const html = renderToStaticMarkup(
      <MountExplorerBreadcrumbs
        mountTitle="Shared Docs"
        normalizedPath="/reports/2026"
        actions={<div>mount-actions</div>}
        onNavigateToPath={onNavigateToPath}
      />,
    );

    expect(html).toContain("mount-actions");
    expect(html).toContain("separator");
    expect(capturedBreadcrumbsItems[0]).toHaveLength(4);
    expect(breadcrumbItemButtonCalls).toHaveLength(3);
    expect(breadcrumbItemButtonCalls[0]).toMatchObject({
      item: expect.objectContaining({ title: "Shared Docs", path: "/" }),
      isActive: false,
    });
    expect(breadcrumbItemButtonCalls[1]).toMatchObject({
      item: expect.objectContaining({ title: "reports", path: "/reports" }),
      isActive: false,
    });
    expect(breadcrumbItemButtonCalls[2]).toMatchObject({
      item: expect.objectContaining({ title: "2026", path: "/reports/2026" }),
      isActive: true,
    });

    (
      breadcrumbItemButtonCalls[0]?.onClick as (() => void) | undefined
    )?.();
    (
      breadcrumbItemButtonCalls[1]?.onClick as (() => void) | undefined
    )?.();

    expect(onNavigateToPath).toHaveBeenNthCalledWith(1, "/");
    expect(onNavigateToPath).toHaveBeenNthCalledWith(2, "/reports");
  });
});

describe("MountExplorerPrimaryAction", () => {
  beforeEach(() => {
    renderedButtons.length = 0;
  });

  it("keeps the primary mounts action wiring intact", () => {
    const onClick = jest.fn();

    const html = renderToStaticMarkup(
      <MountExplorerPrimaryAction label="Import" onClick={onClick} disabled={true} />,
    );

    expect(html).toContain("Import");
    expect(renderedButtons[0]).toMatchObject({
      disabled: true,
      children: "Import",
    });
    (renderedButtons[0]?.onClick as (() => void) | undefined)?.();
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
