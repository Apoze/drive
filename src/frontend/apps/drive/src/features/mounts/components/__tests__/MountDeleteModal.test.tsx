import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType } from "@/features/drivers/types";
import { getDriver } from "@/features/config/Config";
import { addToast } from "@/features/ui/components/toaster/Toaster";
import type { MountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";
import { MountDeleteModal } from "../MountDeleteModal";

const renderedButtons: Array<Record<string, unknown>> = [];
const renderedModals: Array<Record<string, unknown>> = [];

let driverMock = {
  deleteMountEntry: jest.fn(),
};

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: {
    children?: React.ReactNode;
    onClick?: () => void;
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
    SMALL: "small",
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

describe("MountDeleteModal", () => {
  beforeEach(() => {
    renderedButtons.length = 0;
    renderedModals.length = 0;
    mockedAddToast.mockReset();
    driverMock = {
      deleteMountEntry: jest.fn(),
    };
    mockedGetDriver.mockReturnValue(driverMock as never);
  });

  it("renders the folder and multi-item copy variants directly on the host", () => {
    renderToStaticMarkup(
      <MountDeleteModal
        isOpen={true}
        onClose={jest.fn()}
        items={[
          buildItem({
            title: "docs",
            type: ItemType.FOLDER,
            mountMeta: {
              normalizedPath: "/docs",
              entryType: "folder",
            },
          }),
        ]}
        onSuccess={jest.fn()}
      />,
    );

    expect(renderedModals[0]?.title).toBe(
      "explorer.mounts.crud.delete.modal.title_folder",
    );

    renderedButtons.length = 0;
    renderedModals.length = 0;

    renderToStaticMarkup(
      <MountDeleteModal
        isOpen={true}
        onClose={jest.fn()}
        items={[
          buildItem(),
          buildItem({
            id: "mount-entry:mount-1:/docs/notes.txt",
            title: "notes.txt",
            filename: "notes.txt",
            path: "/docs/notes.txt",
            mountMeta: {
              normalizedPath: "/docs/notes.txt",
            },
          }),
        ]}
        onSuccess={jest.fn()}
      />,
    );

    expect(renderedModals[0]?.title).toBe(
      "explorer.mounts.bulk.delete.modal.title_multiple",
    );
  });

  it("keeps the selection guard local for mixed/undeletable selections", async () => {
    renderToStaticMarkup(
      <MountDeleteModal
        isOpen={true}
        onClose={jest.fn()}
        items={[
          buildItem(),
          buildItem({
            id: "mount-entry:mount-2:/other/report.txt",
            mountMeta: {
              mountId: "mount-2",
              normalizedPath: "/other/report.txt",
            },
          }),
        ]}
        onSuccess={jest.fn()}
      />,
    );

    (findButton("explorer.item.actions.delete")?.onClick as (() => void) | undefined)?.();
    await flushAsync();

    expect(driverMock.deleteMountEntry).not.toHaveBeenCalled();
    expect(renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as React.ReactElement)).toContain(
      "explorer.mounts.bulk.delete.mixed_mount",
    );
  });

  it("handles partial failure after successful deletions", async () => {
    const folder = buildItem({
      id: "mount-entry:mount-1:/docs/folder",
      title: "folder",
      type: ItemType.FOLDER,
      mountMeta: {
        normalizedPath: "/docs/folder",
        entryType: "folder",
      },
    });
    const child = buildItem({
      id: "mount-entry:mount-1:/docs/folder/child.txt",
      title: "child.txt",
      filename: "child.txt",
      path: "/docs/folder/child.txt",
      mountMeta: {
        normalizedPath: "/docs/folder/child.txt",
      },
    });

    const onClose = jest.fn();
    const onSuccess = jest.fn();

    driverMock.deleteMountEntry
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new Error("boom"));

    renderToStaticMarkup(
      <MountDeleteModal
        isOpen={true}
        onClose={onClose}
        items={[folder, child]}
        onSuccess={onSuccess}
      />,
    );

    (findButton("explorer.item.actions.delete")?.onClick as (() => void) | undefined)?.();
    await flushAsync();

    expect(driverMock.deleteMountEntry).toHaveBeenNthCalledWith(1, {
      mountId: "mount-1",
      path: "/docs/folder/child.txt",
    });
    expect(driverMock.deleteMountEntry).toHaveBeenNthCalledWith(2, {
      mountId: "mount-1",
      path: "/docs/folder",
    });
    expect(onSuccess).toHaveBeenCalledWith({
      deletedItems: [child],
      partialFailure: {
        item: folder,
        completedCount: 1,
        error: expect.any(Error),
      },
    });
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(mockedAddToast).toHaveBeenCalledTimes(2);
    expect(renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as React.ReactElement)).toContain(
      "explorer.actions.delete.toast",
    );
    expect(renderToStaticMarkup(mockedAddToast.mock.calls[1][0] as React.ReactElement)).toContain(
      "explorer.mounts.bulk.delete.partial_error",
    );
  });
});
