import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { getDriver } from "@/features/config/Config";
import { addToast } from "@/features/ui/components/toaster/Toaster";
import { MountCreateFolderModal } from "../MountCreateFolderModal";

const renderedModals: Array<Record<string, unknown>> = [];
const resetMock = jest.fn();
const registerRefMock = jest.fn();
const focusMock = jest.fn();

let nextSubmitValues = { title: "Projects" };
let submitCreateFolderForm: (() => Promise<void>) | undefined;
let driverMock = {
  createMountFolder: jest.fn(),
};

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: ({ children }: { children?: React.ReactNode }) => <button>{children}</button>,
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

jest.mock("react-hook-form", () => ({
  FormProvider: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  useForm: () => ({
    register: () => ({
      name: "title",
      onChange: jest.fn(),
      onBlur: jest.fn(),
      ref: registerRefMock,
    }),
    handleSubmit: (onSubmit: (data: { title: string }) => Promise<void>) => {
      submitCreateFolderForm = async () => onSubmit(nextSubmitValues);
      return submitCreateFolderForm;
    },
    reset: resetMock,
  }),
}));

jest.mock("@/features/forms/components/RhfInput", () => ({
  RhfInput: (props: { ref?: (element: HTMLInputElement | null) => void; label?: string }) => {
    props.ref?.({
      focus: focusMock,
      value: "",
    } as never);
    return <input aria-label={props.label} />;
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

describe("MountCreateFolderModal", () => {
  beforeEach(() => {
    renderedModals.length = 0;
    resetMock.mockReset();
    registerRefMock.mockReset();
    focusMock.mockReset();
    mockedAddToast.mockReset();
    nextSubmitValues = { title: "Projects" };
    submitCreateFolderForm = undefined;
    driverMock = {
      createMountFolder: jest.fn(),
    };
    mockedGetDriver.mockReturnValue(driverMock as never);
  });

  it("focuses the first input and submits success with reset and close", async () => {
    const onClose = jest.fn();
    const onSuccess = jest.fn();
    const entry = { normalized_path: "/docs/Projects" };
    driverMock.createMountFolder.mockResolvedValue(entry);

    const html = renderToStaticMarkup(
      <MountCreateFolderModal
        isOpen={true}
        onClose={onClose}
        mountId="mount-1"
        parentPath="/docs"
        onSuccess={onSuccess}
      />,
    );

    expect(html).toContain("explorer.actions.createFolder.modal.title");
    expect(focusMock).toHaveBeenCalledTimes(1);

    await submitCreateFolderForm?.();

    expect(driverMock.createMountFolder).toHaveBeenCalledWith({
      mountId: "mount-1",
      path: "/docs",
      name: "Projects",
    });
    expect(resetMock).toHaveBeenCalledTimes(1);
    expect(onSuccess).toHaveBeenCalledWith(entry);
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as React.ReactElement)).toContain(
      "explorer.mounts.create_folder.success",
    );
  });

  it("keeps the error toast path local on submit failure", async () => {
    driverMock.createMountFolder.mockRejectedValue(new Error("boom"));

    renderToStaticMarkup(
      <MountCreateFolderModal
        isOpen={true}
        onClose={jest.fn()}
        mountId="mount-1"
        parentPath="/docs"
        onSuccess={jest.fn()}
      />,
    );

    await submitCreateFolderForm?.();

    expect(mockedAddToast).toHaveBeenCalledTimes(1);
    expect(renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as React.ReactElement)).toContain(
      "normalized-error",
    );
    expect(resetMock).not.toHaveBeenCalled();
  });
});
