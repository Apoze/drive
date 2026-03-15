import { test } from "./fixtures/scenarios";
import { openWorkspaceFromMyFiles } from "./utils-navigate";
import {
  closeFilePreview,
  createEditorFileFromMoreFormats,
  waitForEditorFrame,
} from "./utils-editor";

const createAndWaitWopi = async ({
  page,
  stem,
  kindLabel,
  extensionLabelRegex,
  expectedFilename,
}: {
  page: import("@playwright/test").Page;
  stem: string;
  kindLabel: "Text document" | "Spreadsheet" | "Presentation";
  extensionLabelRegex: RegExp;
  expectedFilename: string;
}) => {
  const start = Date.now();
  const filePreview = await createEditorFileFromMoreFormats({
    page,
    stem,
    kindLabel,
    extensionLabelRegex,
  });
  await waitForEditorFrame({
    filePreview,
    iframe: filePreview.locator("iframe"),
  });

  const firstOpenMs = Date.now() - start;
  console.log(`wopi_onlyoffice_first_open_ms file=${expectedFilename} ms=${firstOpenMs}`);

  await closeFilePreview(page);
};

test.setTimeout(2 * 60 * 1000);

test("ONLYOFFICE editnew: new OOXML loads fast", async ({ page, isolatedWorkspace }) => {
  await page.goto("/");
  await openWorkspaceFromMyFiles(page, isolatedWorkspace.result.workspace_root.title);

  const stamp = isolatedWorkspace.scope.scenario_slug;

  await createAndWaitWopi({
    page,
    stem: `onlyoffice-editnew-docx-${stamp}`,
    kindLabel: "Text document",
    extensionLabelRegex: /\.docx\b/i,
    expectedFilename: `onlyoffice-editnew-docx-${stamp}.docx`,
  });

  await createAndWaitWopi({
    page,
    stem: `onlyoffice-editnew-xlsx-${stamp}`,
    kindLabel: "Spreadsheet",
    extensionLabelRegex: /\.xlsx\b/i,
    expectedFilename: `onlyoffice-editnew-xlsx-${stamp}.xlsx`,
  });

  await createAndWaitWopi({
    page,
    stem: `onlyoffice-editnew-pptx-${stamp}`,
    kindLabel: "Presentation",
    extensionLabelRegex: /\.pptx\b/i,
    expectedFilename: `onlyoffice-editnew-pptx-${stamp}.pptx`,
  });
});
