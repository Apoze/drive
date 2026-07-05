import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useArchiveExtractionStatus } from "@/features/explorer/api/useArchiveExtraction";
import { useArchiveZipStatus } from "@/features/explorer/api/useArchiveZip";
import { ArchiveJobToast } from "../ArchiveJobToast";
import { useArchiveJobLifecycleController } from "../archiveJobLifecycleController";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@/features/explorer/api/useArchiveExtraction", () => ({
  useArchiveExtractionStatus: jest.fn(),
}));

jest.mock("@/features/explorer/api/useArchiveZip", () => ({
  useArchiveZipStatus: jest.fn(),
}));

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  addToast: jest.fn(),
  ToasterItem: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock("react-toastify", () => ({
  toast: jest.fn(),
}));

jest.mock("../archiveJobLifecycleController", () => ({
  useArchiveJobLifecycleController: jest.fn(),
}));

const mockedUseArchiveExtractionStatus = jest.mocked(useArchiveExtractionStatus);
const mockedUseArchiveZipStatus = jest.mocked(useArchiveZipStatus);
const mockedUseArchiveJobLifecycleController = jest.mocked(
  useArchiveJobLifecycleController,
);

describe("ArchiveJobToast", () => {
  beforeEach(() => {
    mockedUseArchiveExtractionStatus.mockReturnValue({
      data: {
        progress: {
          bytes_done: 5,
          bytes_total: 10,
          files_done: 1,
          total: 2,
        },
        state: "running",
      },
    } as never);
    mockedUseArchiveZipStatus.mockReturnValue({
      data: {
        progress: {
          bytes_done: 1,
          bytes_total: 4,
          files_done: 1,
          total: 4,
        },
        state: "running",
      },
    } as never);
  });

  it("delegates unzip lifecycle handling to the shared controller", () => {
    const html = renderToStaticMarkup(
      <ArchiveJobToast
        closeToast={jest.fn()}
        data={undefined}
        kind="unzip"
        isPaused={false}
        jobId="job-unzip"
        destinationFolderId="folder-1"
        toastProps={{} as never}
      />,
    );

    expect(mockedUseArchiveJobLifecycleController).toHaveBeenCalledWith(
      expect.objectContaining({
        destinationFolderId: "folder-1",
        jobId: "job-unzip",
        status: mockedUseArchiveExtractionStatus.mock.results[0]?.value.data,
      }),
    );
    expect(html).toContain("explorer.actions.archive.unzip.toast_running");
  });

  it("delegates zip lifecycle handling to the shared controller", () => {
    const html = renderToStaticMarkup(
      <ArchiveJobToast
        closeToast={jest.fn()}
        data={undefined}
        kind="zip"
        isPaused={false}
        jobId="job-zip"
        destinationFolderId="folder-2"
        toastProps={{} as never}
      />,
    );

    expect(mockedUseArchiveJobLifecycleController).toHaveBeenCalledWith(
      expect.objectContaining({
        destinationFolderId: "folder-2",
        jobId: "job-zip",
        status: mockedUseArchiveZipStatus.mock.results[1]?.value.data,
      }),
    );
    expect(html).toContain("explorer.actions.archive.zip.toast_running");
  });
});
