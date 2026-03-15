import { createHash } from "crypto";
import type { TestInfo, WorkerInfo } from "@playwright/test";

type WorkerScopeInfo = Pick<WorkerInfo, "project" | "workerIndex">;

const compactScopeId = (value: string, maxLength: number) => {
  const raw = String(value || "").trim().toLowerCase();
  const normalized = raw.replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "scope";
  const digest = createHash("sha1").update(raw).digest("hex").slice(0, 8);
  const prefixLength = Math.max(1, maxLength - digest.length - 1);
  const prefix = normalized.slice(0, prefixLength).replace(/^-+|-+$/g, "") || "scope";
  return `${prefix}-${digest}`;
};

export const getPlaywrightRunId = () => {
  return process.env.E2E_RUN_ID || "playwright-local";
};

export const getWorkerId = (workerInfo: WorkerScopeInfo) => {
  return compactScopeId(
    `${workerInfo.project.name}-worker-${workerInfo.workerIndex}`,
    64,
  );
};

export const getScenarioId = (testInfo: TestInfo, suffix?: string) => {
  return compactScopeId(
    [
      testInfo.project.name,
      testInfo.file,
      testInfo.title,
      suffix,
      testInfo.retry ? `retry-${testInfo.retry}` : "",
    ]
      .filter(Boolean)
      .join(" "),
    96,
  );
};

export const getActorKey = (testInfo: TestInfo, suffix?: string) => {
  return compactScopeId(
    [
      testInfo.project.name,
      testInfo.file,
      testInfo.title,
      suffix,
    ]
      .filter(Boolean)
      .join(" "),
    64,
  );
};

export const getStorageStateKey = (
  runId: string,
  workerId: string,
  actorKey: string,
) => {
  return compactScopeId(
    `${runId}-${workerId}-${actorKey}-storage-state`,
    64,
  );
};
