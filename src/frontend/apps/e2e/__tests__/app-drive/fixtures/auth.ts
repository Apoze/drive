import fs from "fs";
import path from "path";
import { test as base, type Browser, type WorkerInfo } from "@playwright/test";

import {
  cleanupScope,
  getE2EApiOrigin,
  getS2SHeaders,
  getStorageState,
  keepE2EScopes,
} from "../utils-common";
import {
  getActorKey,
  getPlaywrightRunId,
  getWorkerId,
} from "./namespaces";
import type {
  BootstrapSessionResponse,
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
  const runId = getPlaywrightRunId();
  const workerId = getWorkerId(workerScope);

  const context = await browser.newContext();
  try {
    const response = await context.request.post(
      `${getE2EApiOrigin()}/api/v1.0/e2e/bootstrap-session/`,
      {
        data: {
          run_id: runId,
          worker_id: workerId,
          actor_key: actorKey,
          email,
          language,
          full_name: fullName,
          short_name: shortName,
        },
        headers: {
          "Content-Type": "application/json",
          ...getS2SHeaders(),
        },
      },
    );

    if (!response.ok()) {
      throw new Error(
        `E2E bootstrap-session failed with status ${response.status()}: ${await response.text()}`,
      );
    }

    const payload = (await response.json()) as BootstrapSessionResponse;
    if (!payload.session.authenticated || !payload.session.csrf_cookie_present) {
      throw new Error("E2E bootstrap-session did not return an authenticated browser session");
    }

    const storageStatePath = getStorageState(payload.scope.storage_state_slug);
    fs.mkdirSync(path.dirname(storageStatePath), { recursive: true });
    await context.storageState({ path: storageStatePath });

    return {
      actorKey,
      runId,
      workerId,
      projectName: workerScope.project.name,
      storageStatePath,
      response: payload,
      actor: payload.actor,
      workspace: payload.workspace,
      scope: payload.scope,
    };
  } finally {
    await context.close();
  }
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
