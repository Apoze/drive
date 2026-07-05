import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { useRouter } from "next/router";
import { useGlobalExplorer } from "../../GlobalExplorerContext";
import { useEntitlementsQuery } from "@/features/entitlements/useEntitlementsQuery";
import { addToast } from "@/features/ui/components/toaster/Toaster";
import {
  AppExplorerBreadcrumbs,
  ExplorerBreadcrumbsMobile,
} from "../AppExplorerBreadcrumbs";

const renderedButtonProps: Array<{
  children?: React.ReactNode;
  onClick?: () => void;
  ["data-testid"]?: string;
}> = [];
const renderedImportDropdownProps: Array<{
  trigger?: React.ReactNode;
}> = [];
const renderedCreateFolderModalProps: Array<{
  parentId?: string;
}> = [];
const renderedBreadcrumbProps: Array<{
  onGoBack?: (item: { id: string }) => void;
}> = [];

const mockRouterPush = jest.fn();
const createFolderModal = {
  isOpen: false,
  open: jest.fn(),
  close: jest.fn(),
};
const importDropdown = {
  isOpen: false,
  setIsOpen: jest.fn(),
};

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: {
    type: "3rdParty",
    init: jest.fn(),
  },
}));

jest.mock("next/router", () => ({
  useRouter: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: {
    children?: React.ReactNode;
    onClick?: () => void;
    ["data-testid"]?: string;
  }) => {
    renderedButtonProps.push(props);
    return <button>{props.children}</button>;
  },
  useModal: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  HorizontalSeparator: () => <div>separator</div>,
  IconSize: {
    MEDIUM: "medium",
    X_SMALL: "x-small",
  },
  useDropdownMenu: () => importDropdown,
}));

jest.mock("../../GlobalExplorerContext", () => ({
  NavigationEventType: {
    ITEM: "item",
  },
  useGlobalExplorer: jest.fn(),
}));

jest.mock("../../embedded-explorer/EmbeddedExplorerGridBreadcrumbs", () => ({
  EmbeddedExplorerGridBreadcrumbs: (props: {
    onGoBack?: (item: { id: string }) => void;
  }) => {
    renderedBreadcrumbProps.push(props);
    return <div>embedded-breadcrumbs</div>;
  },
}));

jest.mock("../../modals/ExplorerCreateFolderModal", () => ({
  ExplorerCreateFolderModal: (props: { parentId?: string }) => {
    renderedCreateFolderModalProps.push(props);
    return <div>create-folder-modal</div>;
  },
}));

jest.mock("../../item-actions/ImportDropdown", () => ({
  ImportDropdown: (props: { trigger?: React.ReactNode }) => {
    renderedImportDropdownProps.push(props);
    return <div>{props.trigger}</div>;
  },
}));

jest.mock("../../icons/ItemIcon", () => ({
  WorkspaceIcon: () => <div>workspace-icon</div>,
}));

jest.mock("../../../hooks/useBreadcrumb", () => ({
  useBreadcrumbQuery: jest.fn(),
}));

jest.mock("@/features/entitlements/useEntitlementsQuery", () => ({
  useEntitlementsQuery: jest.fn(),
}));

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  addToast: jest.fn(),
  ToasterItem: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock("@/utils/defaultRoutes", () => {
  const actual = jest.requireActual("@/utils/defaultRoutes");
  return actual;
});

const mockedUseModal = jest.mocked(useModal);
const mockedUseRouter = jest.mocked(useRouter);
const mockedUseGlobalExplorer = jest.mocked(useGlobalExplorer);
const mockedUseEntitlementsQuery = jest.mocked(useEntitlementsQuery);
const mockedAddToast = jest.mocked(addToast);

const { useBreadcrumbQuery } = jest.requireMock("../../../hooks/useBreadcrumb") as {
  useBreadcrumbQuery: jest.Mock;
};

describe("AppExplorerBreadcrumbs family", () => {
  beforeEach(() => {
    renderedButtonProps.length = 0;
    renderedImportDropdownProps.length = 0;
    renderedCreateFolderModalProps.length = 0;
    renderedBreadcrumbProps.length = 0;
    createFolderModal.open.mockReset();
    importDropdown.setIsOpen.mockReset();
    mockRouterPush.mockReset();
    mockedAddToast.mockReset();
    mockedUseModal.mockReturnValue(createFolderModal as never);
    mockedUseRouter.mockReturnValue({
      pathname: "/explorer/items/my-files",
      push: mockRouterPush,
    } as never);
    mockedUseGlobalExplorer.mockReturnValue({
      item: {
        id: "folder-1",
        title: "Folder",
        abilities: {
          children_create: true,
        },
      },
      onNavigate: jest.fn(),
    } as never);
    mockedUseEntitlementsQuery.mockReturnValue({
      data: {
        can_upload: {
          result: true,
          message: "",
        },
      },
    } as never);
    useBreadcrumbQuery.mockReturnValue({
      data: [
        {
          id: "workspace-1",
          title: "Workspace",
          path: "",
          depth: 0,
          main_workspace: false,
        },
        {
          id: "my-files",
          title: "My files",
          path: "",
          depth: 1,
          main_workspace: false,
        },
        {
          id: "folder-1",
          title: "Folder",
          path: "",
          depth: 2,
          main_workspace: false,
        },
      ],
    });
  });

  it("keeps import/create actions wired on desktop breadcrumbs", () => {
    renderToStaticMarkup(<AppExplorerBreadcrumbs />);

    const importButton = renderedButtonProps.find(
      (button) => button.children === "explorer.tree.import.label",
    );
    const createFolderButton = renderedButtonProps.find(
      (button) => button["data-testid"] === "create-folder-button",
    );

    importButton?.onClick?.();
    createFolderButton?.onClick?.();

    expect(renderedImportDropdownProps).toHaveLength(1);
    expect(importDropdown.setIsOpen).toHaveBeenCalledWith(true);
    expect(createFolderModal.open).toHaveBeenCalled();
    expect(renderedCreateFolderModalProps).toEqual([
      expect.objectContaining({
        parentId: "folder-1",
      }),
    ]);
  });

  it("shows the low-rights upload toast instead of opening the import dropdown", () => {
    mockedUseEntitlementsQuery.mockReturnValue({
      data: {
        can_upload: {
          result: false,
          message: "no-upload",
        },
      },
    } as never);

    renderToStaticMarkup(<AppExplorerBreadcrumbs />);

    const importButton = renderedButtonProps.find(
      (button) => button.children === "explorer.tree.import.label",
    );

    importButton?.onClick?.();

    expect(mockedAddToast).toHaveBeenCalledTimes(1);
    expect(importDropdown.setIsOpen).not.toHaveBeenCalled();
  });

  it("keeps mobile back navigation routed through default routes and item navigation", () => {
    const onNavigate = jest.fn();
    mockedUseGlobalExplorer.mockReturnValue({
      item: {
        id: "folder-1",
        title: "Folder",
      },
      onNavigate,
    } as never);

    renderToStaticMarkup(<ExplorerBreadcrumbsMobile />);

    const backButton = renderedButtonProps[0];
    backButton?.onClick?.();

    expect(mockRouterPush).toHaveBeenCalledWith("/explorer/items/my-files");

    useBreadcrumbQuery.mockReturnValue({
      data: [
        {
          id: "workspace-1",
          title: "Workspace",
          path: "",
          depth: 0,
          main_workspace: false,
        },
        {
          id: "folder-parent",
          title: "Parent",
          path: "",
          depth: 1,
          main_workspace: false,
        },
        {
          id: "folder-1",
          title: "Folder",
          path: "",
          depth: 2,
          main_workspace: false,
        },
      ],
    });
    renderedButtonProps.length = 0;
    mockRouterPush.mockReset();

    renderToStaticMarkup(<ExplorerBreadcrumbsMobile />);
    renderedButtonProps[0]?.onClick?.();

    expect(onNavigate).toHaveBeenCalledWith({
      type: "item",
      item: expect.objectContaining({
        id: "folder-parent",
      }),
    });
  });
});
