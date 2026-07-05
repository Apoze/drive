import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType } from "@/features/drivers/types";
import { getDriver } from "@/features/config/Config";
import { addToast } from "@/features/ui/components/toaster/Toaster";
import type { MountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";
import { MountRenameModal } from "../MountRenameModal";

const renderedForms: Array<Record<string, unknown>> = [];
const capturedUseFormArgs: Array<Record<string, unknown> | undefined> = [];
const focusMock = jest.fn();
const selectionRangeMock = jest.fn();

let currentInputValue = "";
let nextSubmitValues = { title: "Renamed" };
let driverMock = {
  renameMountEntry: jest.fn(),
};

jest.mock("react", () => {
  const actual = jest.requireActual("react");

  return {
    ...actual,
    createElement: (
      type: unknown,
      props: Record<string, unknown>,
      ...children: unknown[]
    ) => {
      if (type === "form" && props?.id === "rename-mount-form") {
        renderedForms.push(props);
      }
      return actual.createElement(type as never, props, ...children);
    },
  };
});

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: {
    type: "3rdParty",
    init: jest.fn(),
  },
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: ({ children }: { children?: React.ReactNode }) => <button>{children}</button>,
  Modal: (props: {
    children?: React.ReactNode;
    rightActions?: React.ReactNode;
    title?: string;
  }) => (
    <div>
      <div>{props.title}</div>
      {props.children}
      {props.rightActions}
    </div>
  ),
  ModalSize: {
    SMALL: "small",
  },
}));

jest.mock("react-hook-form", () => ({
  FormProvider: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  useForm: (args?: Record<string, unknown>) => {
    capturedUseFormArgs.push(args);
    currentInputValue = String(
      (args?.defaultValues as { title?: string } | undefined)?.title ?? "",
    );
    return {
      register: () => ({
        name: "title",
        onChange: jest.fn(),
        onBlur: jest.fn(),
        ref: jest.fn(),
      }),
      handleSubmit: (onSubmit: (data: { title: string }) => Promise<void>) => async () =>
        onSubmit(nextSubmitValues),
    };
  },
}));

jest.mock("@/features/forms/components/RhfInput", () => ({
  RhfInput: (props: { ref?: (element: HTMLInputElement | null) => void; label?: string }) => {
    props.ref?.({
      focus: focusMock,
      setSelectionRange: selectionRangeMock,
      value: currentInputValue,
    } as never);
    return <input aria-label={props.label} defaultValue={currentInputValue} />;
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

describe("MountRenameModal", () => {
  beforeEach(() => {
    renderedForms.length = 0;
    capturedUseFormArgs.length = 0;
    focusMock.mockReset();
    selectionRangeMock.mockReset();
    mockedAddToast.mockReset();
    nextSubmitValues = { title: "Renamed" };
    driverMock = {
      renameMountEntry: jest.fn(),
    };
    mockedGetDriver.mockReturnValue(driverMock as never);
  });

  it("keeps default value and selection behavior for file rename", () => {
    renderToStaticMarkup(
      <MountRenameModal
        isOpen={true}
        onClose={jest.fn()}
        item={buildItem()}
        onSuccess={jest.fn()}
      />,
    );

    expect(capturedUseFormArgs[0]).toMatchObject({
      defaultValues: { title: "report" },
    });
    expect(focusMock).toHaveBeenCalledTimes(1);
    expect(selectionRangeMock).toHaveBeenCalledWith(0, "report".length);
  });

  it("keeps folder default title unchanged", () => {
    renderToStaticMarkup(
      <MountRenameModal
        isOpen={true}
        onClose={jest.fn()}
        item={buildItem({
          title: "docs",
          type: ItemType.FOLDER,
          mountMeta: {
            normalizedPath: "/docs",
            entryType: "folder",
          },
        })}
        onSuccess={jest.fn()}
      />,
    );

    expect(capturedUseFormArgs[0]).toMatchObject({
      defaultValues: { title: "docs" },
    });
  });

  it("preserves known extension on successful submit", async () => {
    const onClose = jest.fn();
    const onSuccess = jest.fn();
    const entry = { normalized_path: "/docs/Renamed.txt" };
    driverMock.renameMountEntry.mockResolvedValue(entry);

    renderToStaticMarkup(
      <MountRenameModal
        isOpen={true}
        onClose={onClose}
        item={buildItem()}
        onSuccess={onSuccess}
      />,
    );

    await (renderedForms[0]?.onSubmit as (() => Promise<void>) | undefined)?.();

    expect(driverMock.renameMountEntry).toHaveBeenCalledWith({
      mountId: "mount-1",
      path: "/docs/report.txt",
      name: "Renamed.txt",
    });
    expect(onSuccess).toHaveBeenCalledWith(entry);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("keeps the error toast path on submit failure", async () => {
    driverMock.renameMountEntry.mockRejectedValue(new Error("boom"));

    renderToStaticMarkup(
      <MountRenameModal
        isOpen={true}
        onClose={jest.fn()}
        item={buildItem()}
        onSuccess={jest.fn()}
      />,
    );

    await (renderedForms[0]?.onSubmit as (() => Promise<void>) | undefined)?.();

    expect(mockedAddToast).toHaveBeenCalledTimes(1);
    expect(renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as React.ReactElement)).toContain(
      "normalized-error",
    );
  });
});
