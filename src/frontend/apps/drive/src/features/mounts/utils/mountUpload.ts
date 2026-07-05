import { APIError } from "@/features/api/APIError";

export type MountUploadSourceLike = {
  name: string;
  path?: string;
  webkitRelativePath?: string;
};

export type MountUploadFolderTask = {
  name: string;
  path: string;
  parentPath: string;
  relativePath: string;
};

export type MountUploadFileTask<T extends MountUploadSourceLike> = {
  file: T;
  parentPath: string;
  relativePath: string;
};

export type MountUploadPlan<T extends MountUploadSourceLike> = {
  folderTasks: MountUploadFolderTask[];
  fileTasks: MountUploadFileTask<T>[];
};

export type MountUploadProgressFile<T extends MountUploadSourceLike> = {
  file: T;
  progress: number;
  status: "in_progress" | "done";
};

export type MountUploadErrorContext =
  | {
      taskType: "folder";
      relativePath: string;
      error: unknown;
    }
  | {
      taskType: "file";
      relativePath: string;
      error: unknown;
    };

export type MountUploadErrorClassification =
  | {
      kind: "folder_conflict_with_file";
      relativePath: string;
    }
  | {
      kind: "file_already_exists";
      relativePath: string;
    }
  | {
      kind: "other";
      relativePath: string;
      backendCode: string | null;
    };

const joinMountPath = (parentPath: string, segment: string) => {
  if (!parentPath || parentPath === "/") {
    return `/${segment}`;
  }

  return `${parentPath.replace(/\/+$/, "")}/${segment}`;
};

const getDepth = (path: string) => path.split("/").filter(Boolean).length;

export const getMountUploadRelativePath = (file: MountUploadSourceLike) => {
  const rawPath = file.webkitRelativePath || file.path || file.name;
  const normalizedPath = rawPath.replace(/\\/g, "/").replace(/^[./]+/, "");

  return normalizedPath || file.name;
};

export const buildMountUploadPlan = <T extends MountUploadSourceLike>({
  currentPath,
  files,
}: {
  currentPath: string;
  files: T[];
}): MountUploadPlan<T> => {
  const folderTasks = new Map<string, MountUploadFolderTask>();
  const fileTasks: MountUploadFileTask<T>[] = [];

  for (const file of files) {
    const relativePath = getMountUploadRelativePath(file);
    const parts = relativePath.split("/").filter(Boolean);
    const parentSegments = parts.slice(0, -1);
    let parentPath = currentPath;

    for (const segment of parentSegments) {
      const nextPath = joinMountPath(parentPath, segment);
      if (!folderTasks.has(nextPath)) {
        folderTasks.set(nextPath, {
          name: segment,
          path: nextPath,
          parentPath,
          relativePath: nextPath.replace(`${currentPath.replace(/\/+$/, "")}/`, ""),
        });
      }
      parentPath = nextPath;
    }

    fileTasks.push({
      file,
      parentPath,
      relativePath,
    });
  }

  return {
    folderTasks: Array.from(folderTasks.values()).sort(
      (left, right) => getDepth(left.path) - getDepth(right.path),
    ),
    fileTasks,
  };
};

export const buildMountUploadProgressFiles = <T extends MountUploadSourceLike>({
  fileTasks,
  completedFileCount = 0,
}: {
  fileTasks: MountUploadPlan<T>["fileTasks"];
  completedFileCount?: number;
}): Record<
  string,
  MountUploadProgressFile<T>
> => {
  return fileTasks.reduce<Record<string, MountUploadProgressFile<T>>>(
    (acc, fileTask, index) => {
      const isDone = index < completedFileCount;
      acc[fileTask.relativePath] = {
        file: fileTask.file,
        progress: isDone ? 100 : 0,
        status: isDone ? "done" : "in_progress",
      };
      return acc;
    },
    {},
  );
};

const getMountUploadBackendCode = (error: unknown) => {
  if (!(error instanceof APIError)) {
    return null;
  }

  return error.data?.errors?.[0]?.code ?? null;
};

export const classifyMountUploadError = ({
  taskType,
  relativePath,
  error,
}: MountUploadErrorContext): MountUploadErrorClassification => {
  const backendCode = getMountUploadBackendCode(error);

  if (
    taskType === "folder" &&
    backendCode === "mount.create_folder.target_exists"
  ) {
    return {
      kind: "folder_conflict_with_file",
      relativePath,
    };
  }

  if (taskType === "file" && backendCode === "mount.upload.target_exists") {
    return {
      kind: "file_already_exists",
      relativePath,
    };
  }

  return {
    kind: "other",
    relativePath,
    backendCode,
  };
};
