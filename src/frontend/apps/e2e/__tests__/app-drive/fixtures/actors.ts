import fs from "fs";
import path from "path";
import { test as base, type Browser, type WorkerInfo } from "@playwright/test";

import {
  E2E_BOOTSTRAP_SESSION_PATH,
  ensureBootstrappedActorSession,
  getE2EApiOrigin,
  getS2SHeaders,
  getStorageState,
  runRequestWithRetry,
} from "../utils-common";
import {
  getPlaywrightRunId,
  getWorkerId,
} from "./namespaces";
import type { BootstrapSessionResponse, WorkerActorFixture } from "./types";

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
  const runId = getPlaywrightRunId();
  const workerId = getWorkerId(workerInfo);

  const context = await browser.newContext();
  try {
    const response = await runRequestWithRetry(() =>
      context.request.post(`${getE2EApiOrigin()}${E2E_BOOTSTRAP_SESSION_PATH}`, {
        data: {
          run_id: runId,
          worker_id: workerId,
          actor_key: actorKey,
        },
        headers: {
          "Content-Type": "application/json",
          ...getS2SHeaders(),
        },
      }),
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

    const meResponse = await runRequestWithRetry(() =>
      context.request.get(`${getE2EApiOrigin()}/api/v1.0/users/me/`),
    );
    if (!meResponse.ok()) {
      throw new Error(
        `E2E bootstrap-session did not yield a usable /users/me session: ${meResponse.status()}`,
      );
    }

    await context.storageState({ path: storageStatePath });
    return {
      actorKey,
      runId,
      workerId,
      projectName: workerInfo.project.name,
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

export const test = base.extend<WorkerFixtures>({
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
