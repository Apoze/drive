import { test as base } from "./actors";
import { cleanupScope, bootstrapScenario, keepE2EScopes } from "../utils-common";
import { getScenarioId } from "./namespaces";
import type {
  BootstrapScenarioResponse,
  CleanupScopeResponse,
  IsolatedWorkspaceFixture,
  MountFixtureTree,
  SearchDatasetFixture,
  SharedWorkspaceFixture,
  WorkerActorFixture,
} from "./types";

type ScenarioFixtures = {
  isolatedWorkspace: IsolatedWorkspaceFixture;
  sharedWorkspace: SharedWorkspaceFixture;
  searchDataset: SearchDatasetFixture;
  mountFixtureTree: MountFixtureTree;
};

const withScenarioLifecycle = async <TFixture>({
  primaryActor,
  cleanupTargets,
  use,
  bootstrap,
}: {
  primaryActor: WorkerActorFixture;
  cleanupTargets?: WorkerActorFixture[];
  use: (fixture: TFixture) => Promise<void>;
  bootstrap: () => Promise<TFixture>;
}) => {
  const fixture = await bootstrap();
  try {
    await use(fixture);
  } finally {
    if (keepE2EScopes()) return;
    const targets = cleanupTargets ?? [primaryActor];
    const cleanedActors = new Set<string>();

    for (const actor of targets) {
      const actorScopeKey = [actor.runId, actor.workerId, actor.actorKey].join(":");
      if (cleanedActors.has(actorScopeKey)) continue;
      cleanedActors.add(actorScopeKey);

      // CRUD specs can move data outside the scenario subtree (for example "move to root"),
      // so fixture teardown must clean the full actor workspace scope, not only one scenario folder.
      await cleanupScope<CleanupScopeResponse>({
        run_id: actor.runId,
        worker_id: actor.workerId,
        actor_key: actor.actorKey,
      });
    }
  }
};

export const test = base.extend<ScenarioFixtures>({
  isolatedWorkspace: async ({ primaryActor }, use, testInfo) => {
    const scenarioId = getScenarioId(testInfo, "isolated-workspace");
    await withScenarioLifecycle({
      primaryActor,
      use,
      bootstrap: async () => {
        const response = await bootstrapScenario<
          BootstrapScenarioResponse<IsolatedWorkspaceFixture["result"]>
        >({
          kind: "isolated_workspace_root",
          run_id: primaryActor.runId,
          worker_id: primaryActor.workerId,
          actor_key: primaryActor.actorKey,
          scenario_id: scenarioId,
        });
        return {
          ...response,
          scenarioId,
        };
      },
    });
  },

  sharedWorkspace: async ({ primaryActor, secondaryActor }, use, testInfo) => {
    const scenarioId = getScenarioId(testInfo, "shared-workspace");
    await withScenarioLifecycle({
      primaryActor,
      cleanupTargets: [primaryActor, secondaryActor],
      use,
      bootstrap: async () => {
        const response = await bootstrapScenario<
          BootstrapScenarioResponse<SharedWorkspaceFixture["result"]>
        >({
          kind: "paired_share",
          run_id: primaryActor.runId,
          worker_id: primaryActor.workerId,
          actor_key: primaryActor.actorKey,
          secondary_actor_key: secondaryActor.actorKey,
          scenario_id: scenarioId,
        });
        return {
          ...response,
          scenarioId,
        };
      },
    });
  },

  searchDataset: async ({ primaryActor }, use, testInfo) => {
    const scenarioId = getScenarioId(testInfo, "search-dataset");
    await withScenarioLifecycle({
      primaryActor,
      use,
      bootstrap: async () => {
        const response = await bootstrapScenario<
          BootstrapScenarioResponse<SearchDatasetFixture["result"]>
        >({
          kind: "search_dataset",
          run_id: primaryActor.runId,
          worker_id: primaryActor.workerId,
          actor_key: primaryActor.actorKey,
          scenario_id: scenarioId,
        });
        return {
          ...response,
          scenarioId,
        };
      },
    });
  },

  mountFixtureTree: async ({ primaryActor }, use, testInfo) => {
    const scenarioId = getScenarioId(testInfo, "mount-fixture-tree");
    await withScenarioLifecycle({
      primaryActor,
      use,
      bootstrap: async () => {
        const response = await bootstrapScenario<
          BootstrapScenarioResponse<MountFixtureTree["result"]>
        >({
          kind: "mount_subtree",
          run_id: primaryActor.runId,
          worker_id: primaryActor.workerId,
          actor_key: primaryActor.actorKey,
          scenario_id: scenarioId,
        });
        return {
          ...response,
          scenarioId,
        };
      },
    });
  },
});
