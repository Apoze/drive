import { expect, Page } from "@playwright/test";
import path from "path";
import { test } from "./fixtures/scenarios";
import {
  getMainWorkspaceBreadcrumbs,
  navigateToFolder,
  openFolderFromMainWorkspace,
} from "./utils-navigate";
import {
  createFolderInCurrentFolder,
  deleteCurrentFolder,
} from "./utils-item";
import {
  clickOnRowItemActions,
  waitForExplorerGridToSettle,
} from "./utils-embedded-grid";
import { expectExplorerBreadcrumbs } from "./utils-explorer";
import {
  expectUploadCancelled,
  getFileRow,
  getFileRowCheckIcon,
  getToastCloseButton,
  getUploadProgressArea,
  getUploadToast,
  mockConfigWithUploadLimit,
  mockSlowUpload,
  mockSlowUploadEnded,
  uploadFile,
} from "./utils/upload-utils";

const PDF_FILE_PATH = path.join(__dirname, "/assets/pv_cm.pdf");
const DOCX_FILE_PATH = path.join(__dirname, "/assets/empty_doc.docx");

test.setTimeout(120_000);

const openUploadWorkspace = async ({
  page,
  workspaceTitle,
  maxMemorySize = 10 * 1024 * 1024,
}: {
  page: Page;
  workspaceTitle: string;
  maxMemorySize?: number;
}) => {
  await mockConfigWithUploadLimit(page, maxMemorySize);
  await page.goto("/");
  await openFolderFromMainWorkspace(page, workspaceTitle);
  await expect(page.getByRole("button", { name: "Import" })).toBeVisible();
};

const fileNameButton = (page: Page, base: string, extension: string) =>
  page
    .getByRole("button", {
      name: new RegExp(`^${base}(?:\\.${extension})?$`),
    })
    .last();

const expectUploadedFileVisible = async (
  page: Page,
  base: string,
  extension: string,
) => {
  await expect(fileNameButton(page, base, extension)).toBeVisible({
    timeout: 20_000,
  });
};

const expectUploadedFileHidden = async (
  page: Page,
  base: string,
  extension: string,
) => {
  await expect(fileNameButton(page, base, extension)).toHaveCount(0);
};

const deleteRowItem = async (page: Page, itemName: string) => {
  await clickOnRowItemActions(page, itemName, /^Delete$/i);
  const confirmDialog = page
    .getByRole("dialog")
    .filter({ has: page.getByRole("button", { name: /^Delete$/i }) })
    .first();

  if (await confirmDialog.isVisible().catch(() => false)) {
    await confirmDialog.getByRole("button", { name: /^Delete$/i }).click();
  }

  await waitForExplorerGridToSettle(page);
};

const navigateBackToBreadcrumbs = async (
  page: Page,
  expectedBreadcrumbs: string[],
) => {
  await page.goBack({ waitUntil: "commit" }).catch(() => undefined);
  await expectExplorerBreadcrumbs(page, expectedBreadcrumbs);
  await waitForExplorerGridToSettle(page);
};

test.describe("File upload behavior", () => {
  test("Shows an error toast and does not upload a file exceeding DATA_UPLOAD_MAX_MEMORY_SIZE", async ({
    page,
    isolatedWorkspace,
  }) => {
    await openUploadWorkspace({
      page,
      workspaceTitle: isolatedWorkspace.result.workspace_root.title,
      maxMemorySize: 1024,
    });

    await uploadFile(page, PDF_FILE_PATH);

    await expect(page.getByText('"pv_cm.pdf" is too large')).toBeVisible();
    await expectUploadedFileHidden(page, "pv_cm", "pdf");
  });

  test("Uploads a file successfully when it is within DATA_UPLOAD_MAX_MEMORY_SIZE", async ({
    page,
    isolatedWorkspace,
  }) => {
    await openUploadWorkspace({
      page,
      workspaceTitle: isolatedWorkspace.result.workspace_root.title,
    });

    await uploadFile(page, PDF_FILE_PATH);

    const uploadToast = getUploadToast(page);
    await expect(uploadToast).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText('"pv_cm.pdf" is too large')).toHaveCount(0);
    await expectUploadedFileVisible(page, "pv_cm", "pdf");
    await expect(getFileRowCheckIcon(page, "pv_cm.pdf")).toBeVisible();
  });

  test("Uploads allowed files and rejects oversized files in the same batch", async ({
    page,
    isolatedWorkspace,
  }) => {
    await openUploadWorkspace({
      page,
      workspaceTitle: isolatedWorkspace.result.workspace_root.title,
      maxMemorySize: 100 * 1024,
    });

    await uploadFile(page, [DOCX_FILE_PATH, PDF_FILE_PATH]);

    await expect(page.getByText('"pv_cm.pdf" is too large')).toBeVisible();
    await expect(getFileRow(page, "empty_doc.docx")).toBeVisible({
      timeout: 20_000,
    });
    await expect(getFileRowCheckIcon(page, "empty_doc.docx")).toBeVisible({
      timeout: 20_000,
    });
    await expectUploadedFileVisible(page, "empty_doc", "docx");
    await expectUploadedFileHidden(page, "pv_cm", "pdf");
  });

  test("Cancels an individual active upload", async ({
    page,
    isolatedWorkspace,
  }) => {
    const { resolve } = await mockSlowUpload(page);
    await openUploadWorkspace({
      page,
      workspaceTitle: isolatedWorkspace.result.workspace_root.title,
    });

    await uploadFile(page, PDF_FILE_PATH);

    await expect(getUploadToast(page)).toBeVisible({ timeout: 20_000 });
    const progressArea = getUploadProgressArea(page, "pv_cm.pdf");
    await expect(progressArea).toBeVisible({ timeout: 20_000 });
    await progressArea.click();

    await expectUploadCancelled(page, "pv_cm.pdf");
    resolve();
    await expectUploadedFileHidden(page, "pv_cm", "pdf");
  });

  test("Cancels an individual upload during finalize", async ({
    page,
    isolatedWorkspace,
  }) => {
    const { resolve } = await mockSlowUploadEnded(page);
    await openUploadWorkspace({
      page,
      workspaceTitle: isolatedWorkspace.result.workspace_root.title,
    });

    await uploadFile(page, PDF_FILE_PATH);

    const progressArea = getUploadProgressArea(page, "pv_cm.pdf");
    await expect(progressArea).toBeVisible({ timeout: 20_000 });
    await progressArea.click();

    await expectUploadCancelled(page, "pv_cm.pdf");
    resolve();
    await expectUploadedFileHidden(page, "pv_cm", "pdf");
  });

  test("Cancels all active and queued uploads from the toast confirmation", async ({
    page,
    isolatedWorkspace,
  }) => {
    const { resolve } = await mockSlowUpload(page);
    await openUploadWorkspace({
      page,
      workspaceTitle: isolatedWorkspace.result.workspace_root.title,
    });

    await uploadFile(page, [PDF_FILE_PATH, DOCX_FILE_PATH]);

    await expect(getFileRow(page, "pv_cm.pdf")).toBeVisible({
      timeout: 20_000,
    });
    await expect(getFileRow(page, "empty_doc.docx")).toBeVisible({
      timeout: 20_000,
    });

    await getToastCloseButton(page).click();
    await expect(page.getByText("Leave upload?")).toBeVisible();
    await page.getByRole("button", { name: "Keep uploading" }).click();
    await expect(page.getByText("Leave upload?")).not.toBeVisible();

    await getToastCloseButton(page).click();
    await page.getByRole("button", { name: "Leave and cancel" }).click();
    await expect(getUploadToast(page)).not.toBeVisible();

    resolve();
    await expectUploadedFileHidden(page, "pv_cm", "pdf");
    await expectUploadedFileHidden(page, "empty_doc", "docx");
  });

  test("Deleting the current folder cancels its active uploads", async ({
    page,
    isolatedWorkspace,
  }) => {
    const { resolve } = await mockSlowUpload(page);
    const rootTitle = isolatedWorkspace.result.workspace_root.title;
    await openUploadWorkspace({ page, workspaceTitle: rootTitle });

    await createFolderInCurrentFolder(page, "UploadTarget");
    await navigateToFolder(
      page,
      "UploadTarget",
      getMainWorkspaceBreadcrumbs(rootTitle, "UploadTarget"),
    );

    await uploadFile(page, PDF_FILE_PATH);
    await expect(getFileRow(page, "pv_cm.pdf")).toBeVisible({
      timeout: 20_000,
    });

    await deleteCurrentFolder(page);
    await expectUploadCancelled(page, "pv_cm.pdf");

    resolve();
    await expectUploadedFileHidden(page, "pv_cm", "pdf");
  });

  test("Deleting an unrelated folder does not cancel another folder upload", async ({
    page,
    isolatedWorkspace,
  }) => {
    const { resolve } = await mockSlowUpload(page);
    const rootTitle = isolatedWorkspace.result.workspace_root.title;
    const rootBreadcrumbs = getMainWorkspaceBreadcrumbs(rootTitle);

    await openUploadWorkspace({ page, workspaceTitle: rootTitle });
    await createFolderInCurrentFolder(page, "FolderA");
    await createFolderInCurrentFolder(page, "FolderB");

    await navigateToFolder(
      page,
      "FolderA",
      getMainWorkspaceBreadcrumbs(rootTitle, "FolderA"),
    );
    await uploadFile(page, PDF_FILE_PATH);
    await expect(getFileRow(page, "pv_cm.pdf")).toBeVisible({
      timeout: 20_000,
    });

    await navigateBackToBreadcrumbs(page, rootBreadcrumbs);
    await deleteRowItem(page, "FolderB");
    await expect(getFileRow(page, "pv_cm.pdf")).toBeVisible();

    resolve();
    await expect(getFileRowCheckIcon(page, "pv_cm.pdf")).toBeVisible({
      timeout: 20_000,
    });
  });

  test("Deleting an ancestor folder cancels nested active uploads", async ({
    page,
    isolatedWorkspace,
  }) => {
    const { resolve } = await mockSlowUpload(page);
    const rootTitle = isolatedWorkspace.result.workspace_root.title;
    const rootBreadcrumbs = getMainWorkspaceBreadcrumbs(rootTitle);

    await openUploadWorkspace({ page, workspaceTitle: rootTitle });
    await createFolderInCurrentFolder(page, "FolderA");
    await navigateToFolder(
      page,
      "FolderA",
      getMainWorkspaceBreadcrumbs(rootTitle, "FolderA"),
    );
    await createFolderInCurrentFolder(page, "FolderB");
    await navigateToFolder(
      page,
      "FolderB",
      getMainWorkspaceBreadcrumbs(rootTitle, "FolderA", "FolderB"),
    );

    await uploadFile(page, PDF_FILE_PATH);
    await expect(getFileRow(page, "pv_cm.pdf")).toBeVisible({
      timeout: 20_000,
    });

    await navigateBackToBreadcrumbs(
      page,
      getMainWorkspaceBreadcrumbs(rootTitle, "FolderA"),
    );
    await navigateBackToBreadcrumbs(page, rootBreadcrumbs);
    await deleteRowItem(page, "FolderA");

    await expectUploadCancelled(page, "pv_cm.pdf");
    resolve();
    await expectUploadedFileHidden(page, "pv_cm", "pdf");
  });
});
