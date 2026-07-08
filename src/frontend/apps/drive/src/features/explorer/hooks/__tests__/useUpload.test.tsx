import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { toast } from "react-toastify";
import { useDropzone } from "react-dropzone";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { useConfig } from "@/features/config/ConfigProvider";
import { useCanCreateChildren } from "@/features/items/utils";
import { useEntitlementsQuery } from "@/features/entitlements/useEntitlementsQuery";
import { getEntitlements } from "@/utils/entitlements";
import { getDriver } from "@/features/config/Config";
import {
  addToast,
} from "@/features/ui/components/toaster/Toaster";
import { useMutationCreateFile, useMutationCreateFolder } from "../useMutations";
import type {
  ItemFolderUpload,
  ItemUploadPlan,
} from "../itemUploadPlan";
import {
  handleUploadHierarchy,
  partitionUploadFilesBySize,
  retryUploadFile,
  shouldPreventUploadUnload,
  UploadingStep,
  useUploadZone,
} from "../useUpload";
import { UploadError } from "@/features/errors/UploadError";

const capturedDropzoneConfigs: Array<Record<string, unknown>> = [];
const capturedUploadToastProps: Array<Record<string, unknown>> = [];
const actualReact = jest.requireActual("react") as typeof React;

jest.mock("react", () => {
  const actual = jest.requireActual("react");
  return {
    ...actual,
    useState: jest.fn(actual.useState),
  };
});

jest.mock("react-dropzone", () => ({
  useDropzone: jest.fn((config) => {
    capturedDropzoneConfigs.push(config);
    return {
      ...config,
      getRootProps: (props: Record<string, unknown>) => props,
      getInputProps: () => ({}),
      isFocused: false,
      isDragAccept: false,
      isDragReject: false,
    };
  }),
}));

jest.mock("react-toastify", () => ({
  toast: {
    dismiss: jest.fn(),
    update: jest.fn(),
  },
}));

jest.mock("react-i18next", () => ({
  useTranslation: jest.fn(),
}));

jest.mock("@tanstack/react-query", () => ({
  useQueryClient: jest.fn(),
}));

jest.mock("@/features/config/ConfigProvider", () => ({
  useConfig: jest.fn(),
}));

jest.mock("@/features/items/utils", () => ({
  useCanCreateChildren: jest.fn(),
}));

jest.mock("@/features/entitlements/useEntitlementsQuery", () => ({
  useEntitlementsQuery: jest.fn(),
}));

jest.mock("@/utils/entitlements", () => ({
  getEntitlements: jest.fn(),
}));

jest.mock("@/features/config/Config", () => ({
  getDriver: jest.fn(),
}));

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  addToast: jest.fn(),
  ToasterItem: ({
    children,
    type,
  }: {
    children?: React.ReactNode;
    type?: string;
  }) => <div data-type={type}>{children}</div>,
}));

jest.mock("../../components/toasts/FileUploadToast", () => ({
  FileUploadToast: (props: Record<string, unknown>) => {
    capturedUploadToastProps.push(props);
    return <div>file-upload-toast</div>;
  },
}));

jest.mock("../useMutations", () => ({
  useMutationCreateFolder: jest.fn(),
  useMutationCreateFile: jest.fn(),
}));

jest.mock("../useRefreshItems", () => ({
  useRefreshQueryCacheAfterMutation: jest.fn(() => jest.fn()),
}));

jest.mock("@/features/explorer/utils/utils", () => ({
  formatSize: (size: number) => `${size} bytes`,
  isIdInItemTree: (itemPath: string, targetId: string) =>
    itemPath.split(".").includes(targetId),
}));

jest.mock("@/features/explorer/utils/dropTraversal", () => ({
  customGetFilesFromEvent: jest.fn(),
  isEmptyFolderMarker: (file: { isEmptyFolder?: boolean }) =>
    file.isEmptyFolder === true,
}));

jest.mock("@/features/api/APIError", () => ({
  errorToString: (error: unknown) =>
    error instanceof Error ? error.message : String(error),
}));

const mockedReact = jest.requireMock("react") as typeof React & {
  useState: jest.Mock;
};
const mockedUseDropzone = jest.mocked(useDropzone);
const mockedUseTranslation = jest.mocked(useTranslation);
const mockedUseQueryClient = jest.mocked(useQueryClient);
const mockedUseConfig = jest.mocked(useConfig);
const mockedUseCanCreateChildren = jest.mocked(useCanCreateChildren);
const mockedUseEntitlementsQuery = jest.mocked(useEntitlementsQuery);
const mockedGetEntitlements = jest.mocked(getEntitlements);
const mockedGetDriver = jest.mocked(getDriver);
const mockedAddToast = jest.mocked(addToast);
const mockedUseMutationCreateFolder = jest.mocked(useMutationCreateFolder);
const mockedUseMutationCreateFile = jest.mocked(useMutationCreateFile);

const buildItem = (id: string) =>
  ({
    id,
    title: `Item ${id}`,
    filename: `Item-${id}.txt`,
    creator: {
      id: "owner-1",
      full_name: "Owner",
      short_name: "OW",
    },
    type: "folder",
    ancestors_link_reach: null,
    ancestors_link_role: null,
    computed_link_reach: null,
    computed_link_role: null,
    upload_state: "ready",
    updated_at: new Date("2026-03-31T00:00:00Z"),
    description: "",
    created_at: new Date("2026-03-31T00:00:00Z"),
    path: `root.${id}`,
    abilities: {
      accesses_manage: false,
      accesses_view: true,
      children_create: true,
      children_list: true,
      destroy: false,
      favorite: false,
      invite_owner: false,
      link_configuration: false,
      media_auth: false,
      move: false,
      link_select_options: {
        restricted: null,
        authenticated: null,
        public: null,
      },
      partial_update: true,
      restore: false,
      retrieve: true,
      tree: false,
      update: true,
      upload_ended: true,
    },
  }) as never;

const buildFileWithPath = (name: string, size: number, path?: string) =>
  ({
    name,
    size,
    path: path ?? name,
  }) as File & { path: string; parentId?: string };

describe("useUpload", () => {
  let driverCreateFile: jest.Mock;
  let driverAbortUpload: jest.Mock;

  beforeEach(() => {
    capturedDropzoneConfigs.length = 0;
    capturedUploadToastProps.length = 0;
    mockedUseDropzone.mockClear();
    mockedReact.useState.mockImplementation(actualReact.useState);
    mockedUseTranslation.mockReturnValue({
      t: (key: string) => key,
    } as never);
    mockedUseQueryClient.mockReturnValue({
      invalidateQueries: jest.fn(),
    } as never);
    mockedUseConfig.mockReturnValue({
      config: {
        DATA_UPLOAD_MAX_MEMORY_SIZE: 10,
      },
    } as never);
    mockedUseCanCreateChildren.mockReturnValue(true);
    mockedUseEntitlementsQuery.mockReturnValue({
      data: {
        can_upload: {
          result: true,
          message: "",
        },
      },
    } as never);
    mockedGetEntitlements.mockResolvedValue({
      can_upload: {
        result: true,
        message: "",
      },
    } as never);
    driverAbortUpload = jest.fn();
    driverCreateFile = jest.fn(({ progressHandler }) => {
      progressHandler?.(100);
      return {
        promise: Promise.resolve({ id: "created-file" }),
        abort: driverAbortUpload,
      };
    });
    mockedGetDriver.mockReturnValue({
      reinitiateFileUpload: jest.fn(),
      createFile: driverCreateFile,
    } as never);
    mockedAddToast.mockReset();
    mockedAddToast.mockReturnValue("toast-1" as never);
    jest.mocked(toast.dismiss).mockReset();
    jest.mocked(toast.update).mockReset();
    mockedUseMutationCreateFolder.mockReturnValue({
      mutate: jest.fn(),
    } as never);
    mockedUseMutationCreateFile.mockReturnValue({
      mutate: jest.fn((_variables, options) => {
        options?.onSettled?.();
      }),
    } as never);
  });

  it("creates upload hierarchy recursively and assigns parent ids to nested files", async () => {
    const invalidateQueries = jest.fn();
    const createFolder = jest.fn(
      (
        variables: { title: string; parentId?: string },
        options: { onSuccess: (createdFolder: { id: string }) => void },
      ) => {
        options.onSuccess({
          id: `${variables.title}-id`,
        } as never);
      },
    );
    const nestedFile = buildFileWithPath("nested.txt", 1, "folder-a/nested.txt");
    const childFolder: ItemFolderUpload = {
      item: { title: "folder-a" },
      files: [nestedFile],
      children: [],
    };
    const upload: ItemUploadPlan = {
      folder: {
        item: buildItem("root"),
        files: [buildFileWithPath("root.txt", 1)],
        children: [childFolder],
        isCurrent: true,
      },
      type: "folder",
      files: [],
    };

    await handleUploadHierarchy({
      item: buildItem("parent-1"),
      upload,
      createFolder: createFolder as never,
      queryClient: { invalidateQueries },
    });

    expect(upload.folder.files[0].parentId).toBe("parent-1");
    expect(nestedFile.parentId).toBe("folder-a-id");
    expect(createFolder).toHaveBeenCalledWith(
      {
        title: "folder-a",
        parentId: "parent-1",
      },
      expect.any(Object),
    );
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["items", "infinite", JSON.stringify({ is_creator_me: true })],
    });
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["items", "parent-1"],
    });
  });

  it("partitions files by max size and exposes the beforeunload guard helper", () => {
    const small = buildFileWithPath("small.txt", 5);
    const large = buildFileWithPath("large.txt", 20);

    expect(
      partitionUploadFilesBySize({ files: [small, large], maxSize: 10 }),
    ).toEqual({
      allowedFiles: [small],
      tooLargeFiles: [large],
    });
    expect(shouldPreventUploadUnload(UploadingStep.NONE)).toBe(false);
    expect(shouldPreventUploadUnload(UploadingStep.CREATE_FOLDERS)).toBe(true);
    expect(shouldPreventUploadUnload(UploadingStep.UPLOAD_FILES)).toBe(true);
  });

  it("retries an upload via reinitiate when an itemId already exists", async () => {
    const setFileMeta = jest.fn();
    const reinitiateFileUpload = jest.fn(async ({ progressHandler }) => {
      progressHandler(42);
    });

    await retryUploadFile({
      path: "folder/file.txt",
      meta: {
        file: buildFileWithPath("file.txt", 2),
        progress: 0,
        itemId: "item-1",
      },
      driver: { reinitiateFileUpload } as never,
      createFile: { mutate: jest.fn() } as never,
      setFileMeta,
    });

    expect(reinitiateFileUpload).toHaveBeenCalledWith({
      itemId: "item-1",
      file: expect.objectContaining({ name: "file.txt" }),
      filename: "file.txt",
      progressHandler: expect.any(Function),
    });
    expect(setFileMeta).toHaveBeenNthCalledWith(1, "folder/file.txt", {
      progress: 0,
      status: "in_progress",
      error: undefined,
    });
    expect(setFileMeta).toHaveBeenNthCalledWith(2, "folder/file.txt", {
      progress: 42,
      status: "in_progress",
    });
    expect(setFileMeta).toHaveBeenNthCalledWith(3, "folder/file.txt", {
      progress: 100,
      status: "done",
    });
  });

  it("retries a new upload via createFile and exposes the failure metadata", async () => {
    const setFileMeta = jest.fn();
    const createFile = {
      mutate: jest.fn((_variables, options) => {
        options?.onError?.(
          new UploadError({
            message: "retry failed",
            kind: "create_failed",
            nextAction: "reinitiate",
            itemId: "item-2",
          }),
        );
      }),
    };

    await retryUploadFile({
      path: "folder/file.txt",
      meta: {
        file: buildFileWithPath("file.txt", 2),
        progress: 0,
      },
      driver: { reinitiateFileUpload: jest.fn() } as never,
      createFile: createFile as never,
      setFileMeta,
    });

    expect(createFile.mutate).toHaveBeenCalledWith(
      expect.objectContaining({
        filename: "file.txt",
      }),
      expect.any(Object),
    );
    expect(setFileMeta).toHaveBeenLastCalledWith("folder/file.txt", {
      status: "failed",
      itemId: "item-2",
      error: {
        message: "retry failed",
        nextAction: "reinitiate",
      },
    });
  });

  it("keeps the dropzone validator coherent with upload rights", () => {
    mockedUseCanCreateChildren.mockReturnValue(false);

    let dropZone: ReturnType<typeof useUploadZone> | undefined;
    const Probe = () => {
      dropZone = useUploadZone({ item: buildItem("parent-1") });
      return <div>probe</div>;
    };

    renderToStaticMarkup(<Probe />);

    const validator = capturedDropzoneConfigs[0]?.validator as () =>
      | { code: string; message: string }
      | null;
    expect(validator()).toEqual({
      code: "no-upload-rights",
      message: "explorer.actions.upload.toast_no_rights",
    });
    expect(dropZone?.dropZone).toBeDefined();
  });

  it("runs the sequential drop flow with entitlements, size filtering and step transitions", async () => {
    const setUploadingState = jest.fn();
    mockedReact.useState.mockImplementationOnce((initial) => [
      initial,
      setUploadingState,
    ]);

    const createFolderMutate = jest.fn(
      (
        variables: { title: string; parentId?: string },
        options: { onSuccess: (folder: { id: string }) => void },
      ) => {
        options.onSuccess({ id: `${variables.title}-id` } as never);
      },
    );
    mockedUseMutationCreateFolder.mockReturnValue({
      mutate: createFolderMutate,
    } as never);

    const Probe = () => {
      useUploadZone({ item: buildItem("parent-1") });
      return <div>probe</div>;
    };

    renderToStaticMarkup(<Probe />);

    const onDrop = capturedDropzoneConfigs[0]?.onDrop as (files: File[]) => Promise<void>;
    const nestedFile = buildFileWithPath("nested.txt", 5, "folder-a/nested.txt");
    const tooLarge = buildFileWithPath("huge.txt", 20, "huge.txt");

    await onDrop([nestedFile, tooLarge]);

    expect(setUploadingState).toHaveBeenCalledWith(expect.any(Function));
    const preparingUpdater = setUploadingState.mock.calls[0][0] as (
      previous: { step: UploadingStep; filesMeta: Record<string, unknown> },
    ) => { step: UploadingStep; filesMeta: Record<string, unknown> };
    expect(preparingUpdater({ step: UploadingStep.NONE, filesMeta: {} }).step).toBe(
      UploadingStep.PREPARING,
    );

    const createFoldersUpdater = setUploadingState.mock.calls[1][0] as (
      previous: { step: UploadingStep; filesMeta: Record<string, unknown> },
    ) => { step: UploadingStep; filesMeta: Record<string, unknown> };
    expect(
      createFoldersUpdater({ step: UploadingStep.PREPARING, filesMeta: {} }).step,
    ).toBe(UploadingStep.CREATE_FOLDERS);

    expect(setUploadingState.mock.calls[2][0]).toMatchObject({
      step: UploadingStep.UPLOAD_FILES,
      filesMeta: {
        "folder-a/nested.txt": expect.objectContaining({
          progress: 0,
          status: "in_progress",
        }),
      },
    });

    const doneUpdater = setUploadingState.mock.calls.at(-1)?.[0] as (
      previous: { step: UploadingStep; filesMeta: Record<string, unknown> },
    ) => { step: UploadingStep; filesMeta: Record<string, unknown> };
    expect(
      doneUpdater({
        step: UploadingStep.UPLOAD_FILES,
        filesMeta: {},
      }).step,
    ).toBe(UploadingStep.DONE);

    expect(createFolderMutate).toHaveBeenCalledWith(
      {
        title: "folder-a",
        parentId: "parent-1",
      },
      expect.any(Object),
    );
    expect(driverCreateFile).toHaveBeenCalledWith(
      expect.objectContaining({
        filename: "nested.txt",
        parentId: "folder-a-id",
      }),
    );
    expect(mockedAddToast).toHaveBeenCalled();
    expect(
      renderToStaticMarkup(mockedAddToast.mock.calls.find((call) =>
        renderToStaticMarkup(call[0] as React.ReactElement).includes(
          "explorer.actions.upload.file_too_large",
        ),
      )?.[0] as React.ReactElement),
    ).toContain("explorer.actions.upload.file_too_large");
  });

  it("stops the drop flow and shows an entitlement error when upload is refused at runtime", async () => {
    const setUploadingState = jest.fn();
    mockedReact.useState.mockImplementationOnce((initial) => [
      initial,
      setUploadingState,
    ]);
    mockedGetEntitlements.mockResolvedValue({
      can_upload: {
        result: false,
        message: "blocked by entitlement",
      },
    } as never);

    const Probe = () => {
      useUploadZone({ item: buildItem("parent-1") });
      return <div>probe</div>;
    };

    renderToStaticMarkup(<Probe />);

    const onDrop = capturedDropzoneConfigs[0]?.onDrop as (files: File[]) => Promise<void>;
    await onDrop([buildFileWithPath("plain.txt", 5)]);

    const preparingUpdater = setUploadingState.mock.calls[0][0] as (
      previous: { step: UploadingStep; filesMeta: Record<string, unknown> },
    ) => { step: UploadingStep; filesMeta: Record<string, unknown> };
    const resetUpdater = setUploadingState.mock.calls[1][0] as (
      previous: { step: UploadingStep; filesMeta: Record<string, unknown> },
    ) => { step: UploadingStep; filesMeta: Record<string, unknown> };

    expect(
      preparingUpdater({ step: UploadingStep.NONE, filesMeta: {} }).step,
    ).toBe(UploadingStep.PREPARING);
    expect(
      resetUpdater({ step: UploadingStep.PREPARING, filesMeta: {} }).step,
    ).toBe(UploadingStep.NONE);
    expect(mockedAddToast).toHaveBeenCalledWith(
      expect.any(Object),
      expect.objectContaining({ autoClose: false }),
    );
    expect(
      mockedAddToast.mock.calls.some((call) =>
        renderToStaticMarkup(call[0] as React.ReactElement).includes(
          "blocked by entitlement",
        ),
      ),
    ).toBe(true);
  });

  it("cancels active regular uploads when the drop target ancestor is deleted", async () => {
    const abortUpload = jest.fn();
    let rejectUpload: (error: unknown) => void = jest.fn();
    driverCreateFile.mockImplementation(({ progressHandler }) => {
      progressHandler?.(10);
      return {
        promise: new Promise((_resolve, reject) => {
          rejectUpload = reject;
        }),
        abort: () => {
          abortUpload();
          rejectUpload(new DOMException("Upload cancelled", "AbortError"));
        },
      };
    });

    let uploadZone: ReturnType<typeof useUploadZone> | undefined;
    const Probe = () => {
      uploadZone = useUploadZone({ item: buildItem("parent-1") });
      return <div>probe</div>;
    };

    renderToStaticMarkup(<Probe />);

    const onDrop = capturedDropzoneConfigs[0]?.onDrop as (
      files: File[],
    ) => Promise<void>;
    const uploadPromise = onDrop([buildFileWithPath("plain.txt", 5)]);

    for (let i = 0; i < 10 && !driverCreateFile.mock.calls.length; i += 1) {
      await Promise.resolve();
    }
    expect(driverCreateFile).toHaveBeenCalled();

    uploadZone?.cancelUploadsForDeletedItems(["parent-1"]);
    await uploadPromise;

    expect(abortUpload).toHaveBeenCalledTimes(1);
  });
});
