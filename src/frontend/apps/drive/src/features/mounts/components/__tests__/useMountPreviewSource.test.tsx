import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useQuery } from "@tanstack/react-query";
import {
  ItemType,
  ItemUploadState,
  LinkReach,
  LinkRole,
} from "@/features/drivers/types";
import type { MountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";
import {
  itemToMountPreviewFile,
  useMountPreviewSource,
} from "../useMountPreviewSource";
import { APIError } from "@/features/api/APIError";

const capturedErrorPreviewProps: Array<{
  onDownload?: () => void;
}> = [];

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@tanstack/react-query", () => ({
  useQuery: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: ({ children }: { children?: React.ReactNode }) => (
    <button>{children}</button>
  ),
}));

jest.mock("@/features/config/ConfigProvider", () => ({
  useConfig: () => ({ config: {} }),
}));

jest.mock("@/features/config/Config", () => ({
  getDriver: () => ({
    getMountWopiInfo: jest.fn(),
    getMountText: jest.fn(),
    saveMountText: jest.fn(),
    getMountPreviewInfo: jest.fn(),
  }),
}));

jest.mock("@/features/operations/timeBounds", () => ({
  getOperationTimeBound: jest.fn(() => ({
    still_working_ms: 1000,
    fail_ms: 2000,
  })),
}));

jest.mock("@/features/operations/useTimeBoundedPhase", () => ({
  useTimeBoundedPhase: jest.fn(() => "loading"),
}));

jest.mock("@/features/api/APIError", () => ({
  APIError: class APIError extends Error {
    code: number;
    data?: unknown;

    constructor(code: number, data?: unknown) {
      super();
      this.code = code;
      this.data = data;
    }
  },
  errorToString: () => "error",
}));

jest.mock("@/features/ui/preview/error/ErrorPreview", () => ({
  ErrorPreview: (props: { onDownload?: () => void }) => {
    capturedErrorPreviewProps.push(props);
    return <div>error-preview</div>;
  },
}));

jest.mock("@/features/ui/preview/archive-viewer/ArchiveViewer", () => ({
  ArchiveViewer: () => <div>archive-viewer</div>,
}));

jest.mock("@/features/mounts/utils/mountExplorerItems", () => ({
  getMountExplorerMeta: (item: { mountMeta: unknown }) => item.mountMeta,
}));

const mockedUseQuery = jest.mocked(useQuery);

const buildMountItem = (): MountExplorerItem => ({
  id: "mount-entry:mount-1:/docs/report.txt",
  title: "report.txt",
  filename: "report.txt",
  creator: {
    id: "mount",
    full_name: "Mount",
    short_name: "MT",
  },
  type: ItemType.FILE,
  ancestors_link_reach: null,
  ancestors_link_role: null,
  computed_link_reach: null,
  computed_link_role: null,
  upload_state: ItemUploadState.READY,
  updated_at: new Date("2026-03-22T00:00:00Z"),
  description: "",
  created_at: new Date("2026-03-22T00:00:00Z"),
  path: "/docs/report.txt",
  url: "http://example.test/download",
  mimetype: "text/plain",
  link_reach: LinkReach.RESTRICTED,
  link_role: LinkRole.READER,
  abilities: {
    accesses_manage: false,
    accesses_view: false,
    children_create: false,
    children_list: false,
    destroy: false,
    favorite: false,
    invite_owner: false,
    link_configuration: false,
    media_auth: false,
    move: false,
    link_select_options: {
      [LinkReach.RESTRICTED]: null,
      [LinkReach.AUTHENTICATED]: null,
      [LinkReach.PUBLIC]: null,
    },
    partial_update: false,
    restore: false,
    retrieve: true,
    tree: false,
    update: false,
    upload_ended: false,
  },
  mountMeta: {
    mountId: "mount-1",
    normalizedPath: "/docs/report.txt",
    entryType: "file",
    mountTitle: "Shared Docs",
    provider: "localfs",
    abilities: {
      children_list: false,
      create_folder: false,
      move: false,
      rename: false,
      destroy: false,
      upload: false,
      duplicate: false,
      download: true,
      preview: true,
      wopi: true,
      share_link_create: false,
    },
  },
});

describe("useMountPreviewSource", () => {
  beforeEach(() => {
    capturedErrorPreviewProps.length = 0;
    mockedUseQuery.mockReset();
    mockedUseQuery.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new APIError(500, {
        errors: [{ code: "mount.wopi.unavailable" }],
      }),
      refetch: jest.fn(),
    } as never);
  });

  it("forwards the preview download callback to the shared WOPI error fallback for mounts", () => {
    const onDownload = jest.fn();
    const file = itemToMountPreviewFile(buildMountItem());

    const Harness = () => {
      const source = useMountPreviewSource();
      return <>{source.renderWopiEditor?.(file, undefined, onDownload)}</>;
    };

    renderToStaticMarkup(<Harness />);

    expect(capturedErrorPreviewProps).toHaveLength(1);
    expect(capturedErrorPreviewProps[0].onDownload).toBe(onDownload);
  });
});
