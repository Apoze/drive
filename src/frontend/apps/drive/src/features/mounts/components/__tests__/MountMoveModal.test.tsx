import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useQuery } from "@tanstack/react-query";
import { ItemType } from "@/features/drivers/types";
import { getDriver } from "@/features/config/Config";
import { addToast } from "@/features/ui/components/toaster/Toaster";
import type { MountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";
import { MountMoveModal } from "../MountMoveModal";

const renderedButtons: Array<Record<string, unknown>> = [];
const renderedModals: Array<Record<string, unknown>> = [];

let driverMock = {
  browseMount: jest.fn(),
  moveMountEntry: jest.fn(),
};

jest.mock("@tanstack/react-query", () => ({
  useQuery: jest.fn(),
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
  Modal: (props: {
    children?: React.ReactNode;
    rightActions?: React.ReactNode;
    title?: string;
  }) => {
    renderedModals.push(props as Record<string, unknown>);
    return (
      <div>
        <div>{props.title}</div>
        {props.children}
        {props.rightActions}
      </div>
    );
  },
  ModalSize: {
    MEDIUM: "medium",
  },
}));

jest.mock("@/features/config/Config", () => ({
  getDriver: jest.fn(() => driverMock),
}));

jest.mock("@/features/api/APIError", () => ({
  errorToString: () => "normalized-error",
}));

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  addToast: jest.fn(),
  ToasterItem: ({
    children,
    type,
  }: {
    children?: React.ReactNode;
    type?: string;
  }) => <div data-type={type ?? "info"}>{children}</div>,
}));

jest.mock("@/features/mounts/utils/mountExplorerItems", () => ({
  getMountTitle: jest.fn(() => "Shared Docs"),
}));

const mockedUseQuery = jest.mocked(useQuery);
const mockedGetDriver = jest.mocked(getDriver);
const mockedAddToast = jest.mocked(addToast);

type BuildItemOverrides = Partial<Omit<MountExplorerItem, "mountMeta">> & {
  mountMeta?: Partial<MountExplorerItem["mountMeta"]>;
};

const buildItem = ({
  mountMeta,
  ...overrides
}: BuildItemOverrides = {}) =>
  ({
    id: "mount-entry:mount-1:/docs/report.txt",
    title: "report.txt",
    filename: "report.txt",
    creator: {
      id: "mount",
      full_name: "Mount",
      short_name: "MT",
    },
    type: ItemType.FILE,
    ancestors_link_reach: null,
    ancestors_link_role: null,
    computed_link_reach: null,
    computed_link_role: null,
    upload_state: "ready",
    updated_at: new Date("2026-03-31T00:00:00Z"),
    description: "",
    created_at: new Date("2026-03-31T00:00:00Z"),
    path: "/docs/report.txt",
    abilities: {
      move: true,
      destroy: true,
    },
    mountMeta: {
      mountId: "mount-1",
      normalizedPath: "/docs/report.txt",
      entryType: "file",
      mountTitle: "Shared Docs",
      provider: "localfs",
      abilities: {
        move: true,
        rename: true,
        destroy: true,
        children_list: true,
      },
      ...mountMeta,
    },
    ...overrides,
  }) as MountExplorerItem;

const findButton = (label: string) =>
  renderedButtons.find((button) => button.children === label);

const flushAsync = async () => {
  await Promise.resolve();
  await Promise.resolve();
};

describe("MountMoveModal", () => {
  beforeEach(() => {
    renderedButtons.length = 0;
    renderedModals.length = 0;
    mockedAddToast.mockReset();
    driverMock = {
      browseMount: jest.fn(),
      moveMountEntry: jest.fn(),
    };
    mockedGetDriver.mockReturnValue(driverMock as never);
  });

  it("renders destination browse surfaces and parent navigation entrypoint", () => {
    mockedUseQuery.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        children: {
          results: [
            {
              name: "child",
              normalized_path: "/docs/child",
              entry_type: "folder",
            },
          ],
        },
      },
    } as never);

    const html = renderToStaticMarkup(
      <MountMoveModal
        isOpen={true}
        onClose={jest.fn()}
        items={[buildItem()]}
        initialDestinationPath="/docs/sub"
        onSuccess={jest.fn()}
      />,
    );

    expect(html).toContain("explorer.mounts.crud.move.modal.destination_label");
    expect(html).toContain("Shared Docs/docs/sub");
    expect(findButton("explorer.mounts.crud.move.modal.parent_folder")).toBeDefined();
    expect(findButton("child")).toBeDefined();
  });

  it("keeps the preflight error path local to the modal", async () => {
    mockedUseQuery.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        children: {
          results: [
            {
              name: "report.txt",
              normalized_path: "/archive/report.txt",
              entry_type: "file",
            },
          ],
        },
      },
    } as never);

    renderToStaticMarkup(
      <MountMoveModal
        isOpen={true}
        onClose={jest.fn()}
        items={[buildItem()]}
        initialDestinationPath="/archive"
        onSuccess={jest.fn()}
      />,
    );

    (findButton("explorer.item.actions.move")?.onClick as (() => void) | undefined)?.();
    await flushAsync();

    expect(driverMock.moveMountEntry).not.toHaveBeenCalled();
    expect(renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as React.ReactElement)).toContain(
      "explorer.mounts.bulk.move.target_conflict",
    );
  });

  it("handles successful multi-move and partial failure without changing semantics", async () => {
    const itemA = buildItem();
    const itemB = buildItem({
      id: "mount-entry:mount-1:/docs/notes.txt",
      title: "notes.txt",
      filename: "notes.txt",
      path: "/docs/notes.txt",
      mountMeta: {
        normalizedPath: "/docs/notes.txt",
      },
    });

    mockedUseQuery.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        children: {
          results: [],
        },
      },
    } as never);

    const onClose = jest.fn();
    const onSuccess = jest.fn();
    driverMock.moveMountEntry
      .mockResolvedValueOnce({ normalized_path: "/archive/report.txt" })
      .mockRejectedValueOnce(new Error("boom"));

    renderToStaticMarkup(
      <MountMoveModal
        isOpen={true}
        onClose={onClose}
        items={[itemA, itemB]}
        initialDestinationPath="/archive"
        onSuccess={onSuccess}
      />,
    );

    (findButton("explorer.item.actions.move")?.onClick as (() => void) | undefined)?.();
    await flushAsync();

    expect(driverMock.moveMountEntry).toHaveBeenNthCalledWith(1, {
      mountId: "mount-1",
      path: "/docs/report.txt",
      targetPath: "/archive",
    });
    expect(driverMock.moveMountEntry).toHaveBeenNthCalledWith(2, {
      mountId: "mount-1",
      path: "/docs/notes.txt",
      targetPath: "/archive",
    });
    expect(onSuccess).toHaveBeenCalledWith({
      sourceItems: [itemA, itemB],
      movedEntries: [{ normalized_path: "/archive/report.txt" }],
      partialFailure: {
        item: itemB,
        completedCount: 1,
        error: expect.any(Error),
      },
    });
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(mockedAddToast).toHaveBeenCalledTimes(2);
    expect(renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as React.ReactElement)).toContain(
      "explorer.actions.move.toast",
    );
    expect(renderToStaticMarkup(mockedAddToast.mock.calls[1][0] as React.ReactElement)).toContain(
      "explorer.mounts.bulk.move.partial_error",
    );
  });
});
