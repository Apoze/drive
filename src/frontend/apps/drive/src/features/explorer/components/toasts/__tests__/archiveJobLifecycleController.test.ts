import { getArchiveJobLifecycleState } from "../archiveJobLifecycleController";

describe("archiveJobLifecycleController", () => {
  it("marks done jobs as terminal and invalidates the destination only on success", () => {
    expect(
      getArchiveJobLifecycleState({
        destinationFolderId: "folder-1",
        jobId: "job-1",
        lastHandledJobId: null,
        status: {
          state: "done",
        },
      }),
    ).toMatchObject({
      shouldHandleTerminal: true,
      shouldInvalidateDestination: true,
      terminalState: "done",
    });
  });

  it("marks failed jobs as terminal without invalidating the destination and dedupes handled jobs", () => {
    expect(
      getArchiveJobLifecycleState({
        destinationFolderId: "folder-1",
        jobId: "job-1",
        lastHandledJobId: null,
        status: {
          errors: [{ detail: "boom" }],
          state: "failed",
        },
      }),
    ).toMatchObject({
      errorDetail: "boom",
      shouldHandleTerminal: true,
      shouldInvalidateDestination: false,
      terminalState: "failed",
    });

    expect(
      getArchiveJobLifecycleState({
        destinationFolderId: "folder-1",
        jobId: "job-1",
        lastHandledJobId: "job-1",
        status: {
          state: "done",
        },
      }).shouldHandleTerminal,
    ).toBe(false);
  });
});
