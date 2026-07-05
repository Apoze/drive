import {
  buildMountUploadPlan,
  buildMountUploadProgressFiles,
  classifyMountUploadError,
  getMountUploadRelativePath,
} from "../mountUpload";
import { APIError } from "@/features/api/APIError";

describe("mountUpload", () => {
  it("normalizes browser relative paths conservatively", () => {
    expect(
      getMountUploadRelativePath({
        name: "report.txt",
        webkitRelativePath: "./team/docs/report.txt",
      }),
    ).toBe("team/docs/report.txt");

    expect(
      getMountUploadRelativePath({
        name: "report.txt",
        path: "\\team\\docs\\report.txt",
      }),
    ).toBe("team/docs/report.txt");

    expect(
      getMountUploadRelativePath({
        name: "report.txt",
      }),
    ).toBe("report.txt");
  });

  it("builds folder creation tasks in parent-first order", () => {
    const plan = buildMountUploadPlan({
      currentPath: "/shared",
      files: [
        {
          name: "report.txt",
          webkitRelativePath: "team/docs/report.txt",
        },
        {
          name: "diagram.png",
          webkitRelativePath: "team/assets/diagram.png",
        },
        {
          name: "notes.txt",
        },
      ],
    });

    expect(plan.folderTasks).toEqual([
      {
        name: "team",
        path: "/shared/team",
        parentPath: "/shared",
        relativePath: "team",
      },
      {
        name: "docs",
        path: "/shared/team/docs",
        parentPath: "/shared/team",
        relativePath: "team/docs",
      },
      {
        name: "assets",
        path: "/shared/team/assets",
        parentPath: "/shared/team",
        relativePath: "team/assets",
      },
    ]);

    expect(plan.fileTasks).toEqual([
      {
        file: {
          name: "report.txt",
          webkitRelativePath: "team/docs/report.txt",
        },
        parentPath: "/shared/team/docs",
        relativePath: "team/docs/report.txt",
      },
      {
        file: {
          name: "diagram.png",
          webkitRelativePath: "team/assets/diagram.png",
        },
        parentPath: "/shared/team/assets",
        relativePath: "team/assets/diagram.png",
      },
      {
        file: {
          name: "notes.txt",
        },
        parentPath: "/shared",
        relativePath: "notes.txt",
      },
    ]);
  });

  it("builds initial progress entries keyed by relative path", () => {
    const plan = buildMountUploadPlan({
      currentPath: "/shared",
      files: [
        {
          name: "report.txt",
          webkitRelativePath: "team/docs/report.txt",
        },
        {
          name: "notes.txt",
        },
      ],
    });

    expect(buildMountUploadProgressFiles({ fileTasks: plan.fileTasks })).toEqual({
      "team/docs/report.txt": {
        file: {
          name: "report.txt",
          webkitRelativePath: "team/docs/report.txt",
        },
        progress: 0,
        status: "in_progress",
      },
      "notes.txt": {
        file: {
          name: "notes.txt",
        },
        progress: 0,
        status: "in_progress",
      },
    });
  });

  it("marks already completed files as done when rebuilding progress state", () => {
    const plan = buildMountUploadPlan({
      currentPath: "/shared",
      files: [
        {
          name: "report.txt",
          webkitRelativePath: "team/docs/report.txt",
        },
        {
          name: "notes.txt",
        },
      ],
    });

    expect(
      buildMountUploadProgressFiles({
        fileTasks: plan.fileTasks,
        completedFileCount: 1,
      }),
    ).toEqual({
      "team/docs/report.txt": {
        file: {
          name: "report.txt",
          webkitRelativePath: "team/docs/report.txt",
        },
        progress: 100,
        status: "done",
      },
      "notes.txt": {
        file: {
          name: "notes.txt",
        },
        progress: 0,
        status: "in_progress",
      },
    });
  });

  it("classifies a folder conflict blocked by an existing file", () => {
    expect(
      classifyMountUploadError({
        taskType: "folder",
        relativePath: "team/docs",
        error: new APIError(400, {
          errors: [
            {
              code: "mount.create_folder.target_exists",
              detail: "Target already exists.",
            },
          ],
        }),
      }),
    ).toEqual({
      kind: "folder_conflict_with_file",
      relativePath: "team/docs",
    });
  });

  it("classifies a file conflict when the destination file already exists", () => {
    expect(
      classifyMountUploadError({
        taskType: "file",
        relativePath: "team/docs/report.txt",
        error: new APIError(400, {
          errors: [
            {
              code: "mount.upload.target_exists",
              detail: "Target already exists.",
            },
          ],
        }),
      }),
    ).toEqual({
      kind: "file_already_exists",
      relativePath: "team/docs/report.txt",
    });
  });

  it("keeps unknown backend failures generic", () => {
    expect(
      classifyMountUploadError({
        taskType: "file",
        relativePath: "team/docs/report.txt",
        error: new APIError(400, {
          errors: [
            {
              code: "mount.upload.failed",
              detail: "Upload failed.",
            },
          ],
        }),
      }),
    ).toEqual({
      kind: "other",
      relativePath: "team/docs/report.txt",
      backendCode: "mount.upload.failed",
    });
  });
});
