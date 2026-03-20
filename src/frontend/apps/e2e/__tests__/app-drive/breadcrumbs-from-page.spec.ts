import { test } from "./fixtures/scenarios";
import { createFolderInCurrentFolder } from "./utils-item";
import { expectExplorerBreadcrumbs } from "./utils-explorer";
import {
  clickToFavorites,
  getMainWorkspaceBreadcrumbs,
  navigateToFolder,
  openFolderFromMainWorkspace,
} from "./utils-navigate";
import { starItem } from "./utils/starred-utils";

test.setTimeout(60_000);

test("Check that the from page is guessed when the user paste a new url in the browser", async ({
  page,
  isolatedWorkspace,
}) => {
  const rootTitle = isolatedWorkspace.result.workspace_root.title;
  const rootId = isolatedWorkspace.result.workspace_root.id;
  await page.goto("/");
  await openFolderFromMainWorkspace(page, rootTitle, rootId);
  await createFolderInCurrentFolder(page, "Bar");

  await createFolderInCurrentFolder(page, "Foo");

  await navigateToFolder(page, "Foo", getMainWorkspaceBreadcrumbs(rootTitle, "Foo"));
  const fooUrl = page.url();

  await openFolderFromMainWorkspace(page, rootTitle, rootId);
  await navigateToFolder(page, "Bar", getMainWorkspaceBreadcrumbs(rootTitle, "Bar"));
  await page.goto(fooUrl, { waitUntil: "domcontentloaded" });
  await expectExplorerBreadcrumbs(page, getMainWorkspaceBreadcrumbs(rootTitle, "Foo"));
});

test("Check that the from page is guessed when the user paste a new url and was browsing favorites", async ({
  page,
  isolatedWorkspace,
}) => {
  const rootTitle = isolatedWorkspace.result.workspace_root.title;
  const rootId = isolatedWorkspace.result.workspace_root.id;
  await page.goto("/");

  await openFolderFromMainWorkspace(page, rootTitle, rootId);
  await createFolderInCurrentFolder(page, "Bar");
  await navigateToFolder(page, "Bar", getMainWorkspaceBreadcrumbs(rootTitle, "Bar"));
  const barUrl = page.url();
  await createFolderInCurrentFolder(page, "Sub Bar");

  await openFolderFromMainWorkspace(page, rootTitle, rootId);

  await createFolderInCurrentFolder(page, "Foo");
  await starItem(page, "Foo");

  await clickToFavorites(page);
  await page.reload();
  await navigateToFolder(page, "Foo", ["Starred", "My files", rootTitle, "Foo"]);

  await page.goto(barUrl, { waitUntil: "domcontentloaded" });

  await expectExplorerBreadcrumbs(page, getMainWorkspaceBreadcrumbs(rootTitle, "Bar"));
  await navigateToFolder(
    page,
    "Sub Bar",
    getMainWorkspaceBreadcrumbs(rootTitle, "Bar", "Sub Bar"),
  );
  await expectExplorerBreadcrumbs(
    page,
    getMainWorkspaceBreadcrumbs(rootTitle, "Bar", "Sub Bar"),
  );
});
