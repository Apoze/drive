import { test as setup } from "@playwright/test";

import { legacyClearDb } from "./utils-common";

// Legacy helper kept as an explicit escape hatch while the suite is migrated
// away from DB-global truncation. `playwright.config.ts` does not wire it in.
setup("clear the database", async () => {
  await legacyClearDb();
});
