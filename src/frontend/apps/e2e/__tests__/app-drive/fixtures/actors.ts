import { test as base, type Browser, type WorkerInfo } from "@playwright/test";

import {
  bootstrapActorSession,
  ensureBootstrappedActorSession,
} from "../utils-common";
import type { WorkerActorFixture } from "./types";

type WorkerFixtures = {
  primaryActor: WorkerActorFixture;
  secondaryActor: WorkerActorFixture;
};

const bootstrapWorkerActor = async ({
  browser,
  actorKey,
  workerInfo,
}: {
  browser: Browser;
  actorKey: string;
  workerInfo: WorkerInfo;
}): Promise<WorkerActorFixture> => {
  return bootstrapActorSession({
    browser,
    workerScope: workerInfo,
    actorKey,
    cleanupMode: "worker",
    verifyUserMe: true,
  });
};

export const test = base.extend<{}, WorkerFixtures>({
  storageState: async ({ primaryActor }, use) => {
    await use(primaryActor.storageStatePath);
  },

  page: async ({ page, primaryActor }, use) => {
    await ensureBootstrappedActorSession(page, primaryActor);
    await use(page);
  },

  primaryActor: [
    async ({ browser }, use, workerInfo) => {
      const actor = await bootstrapWorkerActor({
        browser,
        actorKey: "primary",
        workerInfo,
      });
      await use(actor);
    },
    { scope: "worker" },
  ],

  secondaryActor: [
    async ({ browser }, use, workerInfo) => {
      const actor = await bootstrapWorkerActor({
        browser,
        actorKey: "secondary",
        workerInfo,
      });
      await use(actor);
    },
    { scope: "worker" },
  ],
});
