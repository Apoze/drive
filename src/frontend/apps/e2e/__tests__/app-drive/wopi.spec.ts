import { expect } from "@playwright/test";
import { test } from "./fixtures/scenarios";
import { openWorkspaceFromMyFiles } from "./utils-navigate";
import {
  closeFilePreview,
  createEditorFileFromMoreFormats,
  waitForEditorFrame,
} from "./utils-editor";
import { grantClipboardPermissions } from "./utils/various-utils";

test("Wopi editor", async ({ page, context, browserName, isolatedWorkspace }) => {
  test.skip(browserName !== "chromium", "Only runs on chromium");
  test.setTimeout(120_000);
  await grantClipboardPermissions(browserName, context);
  await page.goto("/");
  await openWorkspaceFromMyFiles(page, isolatedWorkspace.result.workspace_root.title);

  const filePreview = await createEditorFileFromMoreFormats({
    page,
    stem: `wopi-odt-${isolatedWorkspace.scope.scenario_slug}`,
    kindLabel: "Text document",
    extensionLabelRegex: /\.odt\b/i,
  });

  await waitForEditorFrame({
    filePreview,
    iframe: filePreview.locator('iframe[name="office_frame"]'),
    timeoutMs: 90_000,
  });

  await closeFilePreview(page);
});
