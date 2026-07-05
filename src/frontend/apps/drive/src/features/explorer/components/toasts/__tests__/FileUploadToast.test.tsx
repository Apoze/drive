import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { FileUploadToast } from "../FileUploadToast";
import type { UploadingState } from "@/features/explorer/hooks/useUpload";

const renderedButtons: Array<{
  children?: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
}> = [];

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@/features/config/ConfigProvider", () => ({
  useConfig: () => ({ config: {} }),
}));

jest.mock("@/features/operations/timeBounds", () => ({
  getOperationTimeBound: jest.fn(() => ({
    still_working_ms: 1000,
    fail_ms: 2000,
  })),
}));

jest.mock("@/features/operations/useTimeBoundedPhase", () => ({
  useTimeBoundedPhase: jest.fn(() => "still_working"),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: ({
    children,
    onClick,
    disabled,
  }: {
    children?: React.ReactNode;
    onClick?: () => void;
    disabled?: boolean;
  }) => {
    renderedButtons.push({ children, onClick, disabled });
    return <button>{children}</button>;
  },
}));

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  ToasterItem: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock("@/features/ui/components/circular-progress/CircularProgress", () => ({
  CircularProgress: ({ progress }: { progress: number }) => <div>{progress}</div>,
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  Spinner: () => <span>spinner</span>,
}));

jest.mock("pretty-bytes", () => ({
  __esModule: true,
  default: (size: number) => `${size} B`,
}));

jest.mock("../../icons/ItemIcon", () => ({
  getIconByMimeType: () => ({ src: "icon.svg" }),
}));

const buildUploadingState = (overrides?: Partial<UploadingState>): UploadingState => ({
  step: UploadingStep.UPLOAD_FILES,
  filesMeta: {
    "docs/report.txt": {
      file: {
        name: "report.txt",
        path: "./docs/report.txt",
        size: 12,
        type: "text/plain",
      } as never,
      progress: 25,
      status: "in_progress",
    },
  },
  ...overrides,
});

describe("FileUploadToast", () => {
  beforeEach(() => {
    renderedButtons.length = 0;
  });

  it("shows the simple mode status directly for folder preparation steps", () => {
    const html = renderToStaticMarkup(
      <FileUploadToast
        uploadingState={buildUploadingState({
          step: UploadingStep.CREATE_FOLDERS,
          filesMeta: {},
        })}
      />,
    );

    expect(html).toContain("explorer.actions.upload.steps.create_folders");
    expect(html).toContain("operations.long_running.still_working");
    expect(html).toContain("spinner");
  });

  it("routes retry through the provided callback for failed files", () => {
    const onRetry = jest.fn();
    const html = renderToStaticMarkup(
      <FileUploadToast
        uploadingState={buildUploadingState({
          filesMeta: {
            "docs/report.txt": {
              file: {
                name: "report.txt",
                path: "./docs/report.txt",
                size: 12,
                type: "text/plain",
              } as never,
              progress: 0,
              status: "failed",
              error: {
                message: "boom",
                nextAction: "retry",
              },
            },
          },
        })}
        onRetry={onRetry}
      />,
    );

    const retryButton = renderedButtons.find(
      (button) => button.children === "explorer.actions.upload.actions.retry",
    );

    expect(html).toContain("report.txt");
    retryButton?.onClick?.();

    expect(onRetry).toHaveBeenCalledWith("docs/report.txt");
  });

  it("keeps the close action disabled while uploads are still in progress", () => {
    renderToStaticMarkup(
      <FileUploadToast
        uploadingState={buildUploadingState()}
        closeToast={jest.fn()}
      />,
    );

    expect(renderedButtons.at(-1)?.disabled).toBe(true);
  });
});
const UploadingStep = {
  NONE: "none" as UploadingState["step"],
  PREPARING: "preparing" as UploadingState["step"],
  CREATE_FOLDERS: "create_folders" as UploadingState["step"],
  UPLOAD_FILES: "upload_files" as UploadingState["step"],
  DONE: "done" as UploadingState["step"],
};
