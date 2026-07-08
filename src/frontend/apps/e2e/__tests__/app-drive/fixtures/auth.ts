import { test as base, type Browser, type WorkerInfo } from "@playwright/test";

import {
  bootstrapActorSession,
  cleanupScope,
  keepE2EScopes,
} from "../utils-common";
import { getActorKey } from "./namespaces";
import type {
  CleanupScopeResponse,
  WorkerActorFixture,
} from "./types";

type AuthOptions = {
  authActorEmail?: string;
  authActorLanguage?: string | null;
  authActorFullName?: string;
  authActorShortName?: string;
};

type AuthFixtures = {
  authActor: WorkerActorFixture;
};

type WorkerScopeInfo = Pick<WorkerInfo, "project" | "workerIndex">;

const bootstrapAuthActor = async ({
  browser,
  workerScope,
  actorKey,
  email,
  language,
  fullName,
  shortName,
}: {
  browser: Browser;
  workerScope: WorkerScopeInfo;
  actorKey: string;
  email?: string;
  language?: string | null;
  fullName?: string;
  shortName?: string;
}): Promise<WorkerActorFixture> => {
  return bootstrapActorSession({
    browser,
    workerScope,
    actorKey,
    email,
    language,
    fullName,
    shortName,
    cleanupMode: "test",
  });
};

export const test = base.extend<AuthOptions & AuthFixtures>({
  authActorEmail: [undefined, { option: true }],
  authActorLanguage: [undefined, { option: true }],
  authActorFullName: [undefined, { option: true }],
  authActorShortName: [undefined, { option: true }],

  storageState: async ({ authActor }, use) => {
    await use(authActor.storageStatePath);
  },

  authActor: async (
    {
      browser,
      authActorEmail,
      authActorLanguage,
      authActorFullName,
      authActorShortName,
    },
    use,
    testInfo,
  ) => {
    const actorKey = getActorKey(testInfo, "auth");
    const actor = await bootstrapAuthActor({
      browser,
      workerScope: testInfo,
      actorKey,
      email: authActorEmail,
      language: authActorLanguage,
      fullName: authActorFullName,
      shortName: authActorShortName,
    });

    try {
      await use(actor);
    } finally {
      if (keepE2EScopes()) return;
      await cleanupScope<CleanupScopeResponse>({
        run_id: actor.runId,
        worker_id: actor.workerId,
        actor_key: actor.actorKey,
      });
    }
  },
});
