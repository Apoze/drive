import { getArchiveViewerJobStatusLabel } from "../archiveViewerJobStatus";

describe("archiveViewerJobStatus", () => {
  it("formats the inline extraction status from the shared archive extraction state", () => {
    const t = jest.fn((key: string) => key);

    expect(
      getArchiveViewerJobStatusLabel({
        status: undefined,
        t,
      }),
    ).toBe("archive_viewer.extract.status_loading");

    expect(
      getArchiveViewerJobStatusLabel({
        status: {
          progress: {
            bytes_done: 5,
            bytes_total: 10,
            files_done: 1,
            total: 2,
          },
          state: "running",
        },
        t,
      }),
    ).toBe("archive_viewer.extract.status");

    expect(t).toHaveBeenNthCalledWith(1, "archive_viewer.extract.status_loading");
    expect(t).toHaveBeenNthCalledWith(2, "archive_viewer.extract.status", {
      done: 1,
      state: "running",
      total: 2,
    });
  });
});
