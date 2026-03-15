export type E2EActor = {
  id: string;
  email: string;
  created?: boolean;
  full_name?: string | null;
  short_name?: string | null;
  language?: string | null;
};

export type E2EItemRef = {
  id: string;
  title: string;
  type: string;
  main_workspace: boolean;
  deleted?: boolean;
};

export type E2ESessionScope = {
  run_id: string;
  worker_id: string;
  actor_key: string;
  run_slug: string;
  worker_slug: string;
  actor_slug: string;
  actor_email: string;
  actor_full_name: string;
  actor_short_name: string;
  actor_short_name_prefix: string;
  storage_state_slug: string;
  mount_run_path: string;
  mount_worker_path: string;
  mount_actor_path: string;
};

export type E2EScenarioScope = E2ESessionScope & {
  scenario_id: string;
  scenario_slug: string;
  mount_root_path: string;
  isolated_workspace_title: string;
  shared_workspace_title: string;
  search_dataset_title: string;
  preview_fixture_title: string;
};

export type BootstrapSessionResponse = {
  scope: E2ESessionScope;
  actor: E2EActor;
  workspace: E2EItemRef;
  session: {
    authenticated: boolean;
    csrf_cookie_name: string;
    csrf_cookie_present: boolean;
  };
};

export type BootstrapScenarioResponse<TResult> = {
  scope: E2EScenarioScope;
  kind: string;
  actor: {
    id: string;
    email: string;
  };
  result: TResult;
};

export type CleanupScopeResponse = {
  scope: Record<string, unknown>;
  cleanup: {
    mode: string;
    deleted_item_count: number;
    deleted_mount_paths?: string[];
  };
};

export type WorkerActorFixture = {
  actorKey: string;
  runId: string;
  workerId: string;
  projectName: string;
  storageStatePath: string;
  response: BootstrapSessionResponse;
  actor: E2EActor;
  workspace: E2EItemRef;
  scope: E2ESessionScope;
};

export type IsolatedWorkspaceFixture = BootstrapScenarioResponse<{
  workspace_root: E2EItemRef;
}> & {
  scenarioId: string;
};

export type SharedWorkspaceFixture = BootstrapScenarioResponse<{
  shared_root: E2EItemRef;
  secondary_actor: {
    id: string;
    email: string;
  };
}> & {
  scenarioId: string;
};

export type SearchDatasetFixture = BootstrapScenarioResponse<{
  dataset_root: E2EItemRef;
  root_entries: E2EItemRef[];
}> & {
  scenarioId: string;
};

export type MountFixtureTree = BootstrapScenarioResponse<{
  mount_id: string;
  root_path: string;
  created_paths: string[];
  io: Record<string, boolean>;
}> & {
  scenarioId: string;
};
