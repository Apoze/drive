import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType } from "@/features/drivers/types";
import { errorToString } from "@/features/api/APIError";
import { showArchiveJobToast } from "@/features/explorer/components/toasts/ArchiveJobToast";
import { addToast } from "@/features/ui/components/toaster/Toaster";
import {
  createArchiveUnzipSubmitController,
  createArchiveZipSubmitController,
  defaultArchiveNameForItems,
  ensureZipSuffix,
  getArchiveFolderName,
} from "../archiveActionSubmitControllers";

jest.mock("@/features/api/APIError", () => ({
  errorToString: jest.fn(),
}));

jest.mock("@/features/explorer/components/toasts/ArchiveJobToast", () => ({
  showArchiveJobToast: jest.fn(),
}));

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  addToast: jest.fn(),
  ToasterItem: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

const mockedErrorToString = jest.mocked(errorToString);
const mockedShowArchiveJobToast = jest.mocked(showArchiveJobToast);
const mockedAddToast = jest.mocked(addToast);

describe("archiveActionSubmitControllers", () => {
  const t = (key: string) => key;

  beforeEach(() => {
    mockedAddToast.mockReset();
    mockedErrorToString.mockReset();
    mockedShowArchiveJobToast.mockReset();
  });

  it("centralizes archive zip defaults from the selected items", () => {
    expect(
      defaultArchiveNameForItems([
        {
          filename: "Quarterly Report.pdf",
          id: "file-1",
          title: "Quarterly Report",
          type: ItemType.FILE,
        } as never,
      ]),
    ).toBe("Quarterly Report.zip");

    expect(
      defaultArchiveNameForItems([
        {
          id: "folder-1",
          title: "Invoices",
          type: ItemType.FOLDER,
        } as never,
      ]),
    ).toBe("Invoices.zip");

    expect(defaultArchiveNameForItems([])).toBe("archive.zip");
    expect(ensureZipSuffix(" report ")).toBe("report.zip");
  });

  it("submits zip payloads, shows the running job toast and closes on success", async () => {
    const mutateAsync = jest.fn().mockResolvedValue({ job_id: "job-zip-1" });
    const onClose = jest.fn();
    const controller = createArchiveZipSubmitController({
      destinationFolderId: "folder-dest",
      itemIds: ["item-1", "item-2"],
      onClose,
      startZip: { mutateAsync },
      t,
    });

    await controller.submitArchiveZip("Reports");

    expect(mutateAsync).toHaveBeenCalledWith({
      archive_name: "Reports.zip",
      destination_folder_id: "folder-dest",
      item_ids: ["item-1", "item-2"],
    });
    expect(mockedShowArchiveJobToast).toHaveBeenCalledWith({
      destinationFolderId: "folder-dest",
      jobId: "job-zip-1",
      kind: "zip",
    });
    expect(onClose).toHaveBeenCalled();
  });

  it("falls back to the translated zip error toast when the zip launch fails", async () => {
    const mutateAsync = jest.fn().mockRejectedValue(new Error("boom"));
    mockedErrorToString.mockReturnValue("");
    const controller = createArchiveZipSubmitController({
      destinationFolderId: "folder-dest",
      itemIds: ["item-1"],
      onClose: jest.fn(),
      startZip: { mutateAsync },
      t,
    });

    await controller.submitArchiveZip("Reports");

    expect(mockedAddToast).toHaveBeenCalledTimes(1);
    expect(renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as never)).toContain(
      "explorer.actions.archive.zip.toast_failed",
    );
  });

  it("derives the default unzip folder name from the archive item", () => {
    expect(
      getArchiveFolderName({
        filename: "Archive Name.zip",
        title: "ignored",
      } as never),
    ).toBe("Archive Name");

    expect(
      getArchiveFolderName({
        filename: "archive.tar.gz",
        title: "ignored",
      } as never),
    ).toBe("archive.tar");
  });

  it("submits unzip payloads, shows the running job toast and closes on success", async () => {
    const mutateAsync = jest.fn().mockResolvedValue({ job_id: "job-unzip-1" });
    const onClose = jest.fn();
    const controller = createArchiveUnzipSubmitController({
      archiveItemId: "archive-1",
      destinationFolderId: "folder-dest",
      onClose,
      startExtraction: { mutateAsync },
      t,
    });

    await controller.submitArchiveExtraction({
      collisionPolicy: "overwrite",
      createRootFolder: false,
    });

    expect(mutateAsync).toHaveBeenCalledWith({
      collision_policy: "overwrite",
      create_root_folder: false,
      destination_folder_id: "folder-dest",
      item_id: "archive-1",
      mode: "all",
    });
    expect(mockedShowArchiveJobToast).toHaveBeenCalledWith({
      destinationFolderId: "folder-dest",
      jobId: "job-unzip-1",
      kind: "unzip",
    });
    expect(onClose).toHaveBeenCalled();
  });

  it("uses the detailed unzip error message when available", async () => {
    const mutateAsync = jest.fn().mockRejectedValue(new Error("boom"));
    mockedErrorToString.mockReturnValue("archive extraction unavailable");
    const controller = createArchiveUnzipSubmitController({
      archiveItemId: "archive-1",
      destinationFolderId: "folder-dest",
      onClose: jest.fn(),
      startExtraction: { mutateAsync },
      t,
    });

    await controller.submitArchiveExtraction({
      collisionPolicy: "rename",
      createRootFolder: true,
    });

    expect(mockedAddToast).toHaveBeenCalledTimes(1);
    expect(renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as never)).toContain(
      "archive extraction unavailable",
    );
  });
});
