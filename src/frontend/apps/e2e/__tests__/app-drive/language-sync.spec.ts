import test, { expect, type TestInfo } from "@playwright/test";

import { clearDb, login } from "./utils-common";

const DEFAULT_E2E_API_ORIGIN = "http://127.0.0.1:8071";

const resolveApiOrigin = (testInfo?: TestInfo) => {
  const envOrigin = process.env.E2E_API_ORIGIN;
  if (envOrigin) return envOrigin;

  const baseUrl = testInfo?.project?.use?.baseURL;
  if (typeof baseUrl === "string") {
    const url = new URL(baseUrl);
    url.port = "8071";
    url.pathname = "";
    url.search = "";
    url.hash = "";
    return url.toString().replace(/\/$/, "");
  }

  return DEFAULT_E2E_API_ORIGIN;
};

const resolveApiBase = (testInfo?: TestInfo) => {
  return new URL("/api/v1.0", resolveApiOrigin(testInfo)).toString();
};

test("Backend user language syncs to browser on load", async ({ page }, testInfo) => {
  await clearDb();
  await login(page, "user-lang@example.com");

  const apiOrigin = resolveApiOrigin(testInfo);
  const apiBase = resolveApiBase(testInfo);

  // Navigate to a stable route and wait for app readiness (avoid localized text).
  try {
    await page.goto("/explorer/items/my-files", { waitUntil: "commit" });
  } catch {
    // SPA navigations can abort the initial `goto` request; rely on URL assertion below.
  }
  await page.waitForURL(/\/explorer\/items\/my-files/, { timeout: 20_000 });
  await expect(page.getByTestId("default-route-button")).toBeVisible({
    timeout: 20_000,
  });

  // Extract the CSRF token from cookies
  const cookies = await page.context().cookies(apiOrigin);
  const csrfToken =
    cookies.find((c) => c.name === "csrftoken")?.value ?? "";
  expect(csrfToken).not.toBe("");

  // Fetch the user id
  const meResponse = await page.request.get(`${apiBase}/users/me/`);
  expect(meResponse.status()).toBe(200);
  const me = await meResponse.json();

  // Set the user's language to French via the API
  const patchResponse = await page.request.patch(
    `${apiBase}/users/${me.id}/`,
    {
    headers: { "X-CSRFToken": csrfToken },
    data: { language: "fr-fr" },
    }
  );
  expect(patchResponse.status()).toBe(200);

  // Reload so the hook picks up the new language
  try {
    await page.goto("/explorer/items/my-files", { waitUntil: "commit" });
  } catch {
    // SPA navigations can abort the initial `goto` request; rely on URL assertion below.
  }
  await page.waitForURL(/\/explorer\/items\/my-files/, { timeout: 20_000 });
  await expect(page.getByTestId("default-route-button")).toBeVisible({
    timeout: 20_000,
  });

  // The app should sync the backend language to the browser (language-independent check).
  await expect
    .poll(
      async () =>
        page.evaluate(() => document.documentElement.getAttribute("lang")),
      { timeout: 10_000 }
    )
    .toBe("fr-FR");
});

test("Browser language syncs to backend for new user", async ({ page }, testInfo) => {
  await clearDb();
  await login(page, "new-user-lang@example.com");

  const apiBase = resolveApiBase(testInfo);

  // Before navigating, the freshly created user should have no language
  const meBefore = await page.request.get(`${apiBase}/users/me/`);
  expect(meBefore.status()).toBe(200);
  const userBefore = await meBefore.json();
  expect(userBefore.language).toBeNull();

  try {
    await page.goto("/explorer/items/my-files", { waitUntil: "commit" });
  } catch {
    // SPA navigations can abort the initial `goto` request; rely on URL assertion below.
  }
  await page.waitForURL(/\/explorer\/items\/my-files/, { timeout: 20_000 });
  await expect(page.getByTestId("default-route-button")).toBeVisible({
    timeout: 20_000,
  });

  // The hook should have synced the browser locale (en-US → en-us) to the backend
  await expect
    .poll(
      async () => {
        const meAfter = await page.request.get(`${apiBase}/users/me/`);
        if (meAfter.status() !== 200) {
          return `status:${meAfter.status()}`;
        }
        const userAfter = await meAfter.json();
        return userAfter.language;
      },
      { timeout: 15_000 }
    )
    .toBe("en-us");
});
