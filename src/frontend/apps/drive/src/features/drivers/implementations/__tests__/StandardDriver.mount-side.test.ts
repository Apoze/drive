import { StandardDriver } from "../StandardDriver";
import { fetchAPI } from "@/features/api/fetchApi";
import { getRuntimeConfig } from "@/features/config/runtimeConfig";
import { getOperationTimeBound } from "@/features/operations/timeBounds";

jest.mock("@/features/api/fetchApi", () => ({
  ensureCsrfCookie: jest.fn(),
  fetchAPI: jest.fn(),
  getCSRFToken: jest.fn(),
}));

jest.mock("@/features/config/runtimeConfig", () => ({
  getRuntimeConfig: jest.fn(),
}));

jest.mock("@/features/operations/timeBounds", () => ({
  getOperationTimeBound: jest.fn(),
}));

const mockedFetchAPI = jest.mocked(fetchAPI);
const mockedGetRuntimeConfig = jest.mocked(getRuntimeConfig);
const mockedGetOperationTimeBound = jest.mocked(getOperationTimeBound);

const makeResponse = <T>(
  data: T,
  params?: {
    status?: number;
    headerEtag?: string | null;
    jsonError?: Error;
  },
) =>
  ({
    status: params?.status ?? 200,
    json: params?.jsonError
      ? jest.fn().mockRejectedValue(params.jsonError)
      : jest.fn().mockResolvedValue(data),
    headers: {
      get: jest.fn().mockImplementation((name: string) =>
        name === "ETag" ? params?.headerEtag ?? null : null,
      ),
    },
  }) as never;

describe("StandardDriver mount-side adapters", () => {
  let driver: StandardDriver;

  beforeEach(() => {
    driver = new StandardDriver();
    mockedFetchAPI.mockReset();
    mockedGetRuntimeConfig.mockReset();
    mockedGetOperationTimeBound.mockReset();
    mockedGetRuntimeConfig.mockReturnValue({ some: "config" } as never);
    mockedGetOperationTimeBound.mockImplementation((operation: string) => {
      const bounds: Record<string, { fail_ms: number; still_working_ms: number }> = {
        wopi_info: { still_working_ms: 50, fail_ms: 505 },
      };
      return bounds[operation];
    });
  });

  it("keeps browseMount defaults and query wiring intact", async () => {
    const browseResponse = {
      mount_id: "mount-1",
      normalized_path: "/",
      capabilities: {},
      entry: {
        mount_id: "mount-1",
        normalized_path: "/",
        entry_type: "folder",
        name: "/",
        abilities: {
          children_list: true,
          create_folder: true,
          move: false,
          rename: false,
          destroy: false,
          upload: true,
          duplicate: false,
          download: false,
          preview: false,
          wopi: false,
          share_link_create: false,
        },
      },
      children: null,
    };
    mockedFetchAPI
      .mockResolvedValueOnce(makeResponse(browseResponse))
      .mockResolvedValueOnce(makeResponse(browseResponse));

    await expect(driver.browseMount({ mountId: "mount-1" })).resolves.toEqual(
      browseResponse,
    );
    await expect(
      driver.browseMount({
        mountId: "mount-1",
        path: "/docs",
        limit: 50,
        offset: 25,
      }),
    ).resolves.toEqual(browseResponse);

    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      1,
      "mounts/mount-1/browse/?path=%2F&limit=20&offset=0",
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      2,
      "mounts/mount-1/browse/?path=%2Fdocs&limit=50&offset=25",
    );
  });

  it("keeps preview/text/WOPI params, redirects and ETag contracts intact", async () => {
    const previewInfo = { kind: "image" };
    const wopiInfo = {
      access_token: "token",
      access_token_ttl: 3600,
      launch_url: "https://office.example.test",
    };
    mockedFetchAPI
      .mockResolvedValueOnce(makeResponse(previewInfo))
      .mockResolvedValueOnce(
        makeResponse(
          {
            content: "hello",
            truncated: false,
            size: 5,
            max_preview_bytes: 100,
            etag: "body-etag",
          },
          { headerEtag: "header-etag" },
        ),
      )
      .mockResolvedValueOnce(
        makeResponse({ etag: "body-only-etag" }, { headerEtag: null }),
      )
      .mockResolvedValueOnce(
        makeResponse({}, { headerEtag: null, jsonError: new Error("no body") }),
      )
      .mockResolvedValueOnce(makeResponse(wopiInfo));

    await expect(
      driver.getMountPreviewInfo({ mountId: "mount-1", path: "/docs/a.png" }),
    ).resolves.toEqual(previewInfo);
    await expect(
      driver.getMountText({ mountId: "mount-1", path: "/docs/a.txt" }),
    ).resolves.toEqual({
      content: "hello",
      truncated: false,
      size: 5,
      max_preview_bytes: 100,
      etag: "header-etag",
    });
    await expect(
      driver.saveMountText({
        mountId: "mount-1",
        path: "/docs/a.txt",
        content: "hello",
        etag: "if-match-etag",
      }),
    ).resolves.toEqual({ etag: "body-only-etag" });
    await expect(
      driver.saveMountText({
        mountId: "mount-1",
        path: "/docs/b.txt",
        content: "world",
        etag: "if-match-etag-2",
      }),
    ).resolves.toEqual({ etag: null });
    await expect(
      driver.getMountWopiInfo({ mountId: "mount-1", path: "/docs/a.docx" }),
    ).resolves.toEqual(wopiInfo);

    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      1,
      "mounts/mount-1/preview-info/",
      { params: { path: "/docs/a.png" } },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      2,
      "mounts/mount-1/text/",
      { params: { path: "/docs/a.txt" } },
      { redirectOn40x: false },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      3,
      "mounts/mount-1/text/",
      {
        method: "PUT",
        params: { path: "/docs/a.txt" },
        headers: { "If-Match": "if-match-etag" },
        body: JSON.stringify({ content: "hello" }),
      },
      { redirectOn40x: false },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      4,
      "mounts/mount-1/text/",
      {
        method: "PUT",
        params: { path: "/docs/b.txt" },
        headers: { "If-Match": "if-match-etag-2" },
        body: JSON.stringify({ content: "world" }),
      },
      { redirectOn40x: false },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      5,
      "mounts/mount-1/wopi/",
      { params: { path: "/docs/a.docx" } },
      { timeoutMs: 505, redirectOn40x: false },
    );
  });

  it("keeps mount-side mutations on their canonical endpoints and redirect contracts", async () => {
    const mountEntry = {
      mount_id: "mount-1",
      normalized_path: "/docs/report.txt",
      entry_type: "file",
      name: "report.txt",
      abilities: {
        children_list: false,
        create_folder: false,
        move: true,
        rename: true,
        destroy: true,
        upload: false,
        duplicate: true,
        download: true,
        preview: true,
        wopi: true,
        share_link_create: true,
      },
    };
    mockedFetchAPI
      .mockResolvedValueOnce(makeResponse({ share_url: "https://share.example.test/mount" }))
      .mockResolvedValueOnce(makeResponse(mountEntry))
      .mockResolvedValueOnce(makeResponse(mountEntry))
      .mockResolvedValueOnce(makeResponse(mountEntry))
      .mockResolvedValueOnce(makeResponse(mountEntry))
      .mockResolvedValueOnce(makeResponse({}, { status: 204 }));

    await expect(
      driver.createMountShareLink({ mountId: "mount-1", path: "/docs/report.txt" }),
    ).resolves.toEqual({ share_url: "https://share.example.test/mount" });
    await expect(
      driver.duplicateMountEntry({ mountId: "mount-1", path: "/docs/report.txt" }),
    ).resolves.toEqual(mountEntry);
    await expect(
      driver.createMountFolder({
        mountId: "mount-1",
        path: "/docs",
        name: "reports",
        reuseExisting: true,
      }),
    ).resolves.toEqual(mountEntry);
    await expect(
      driver.renameMountEntry({
        mountId: "mount-1",
        path: "/docs/report.txt",
        name: "report-renamed.txt",
      }),
    ).resolves.toEqual(mountEntry);
    await expect(
      driver.moveMountEntry({
        mountId: "mount-1",
        path: "/docs/report.txt",
        targetPath: "/archive",
      }),
    ).resolves.toEqual(mountEntry);
    await expect(
      driver.deleteMountEntry({ mountId: "mount-1", path: "/docs/report.txt" }),
    ).resolves.toBeUndefined();

    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      1,
      "mounts/mount-1/share-links/",
      {
        method: "POST",
        body: JSON.stringify({ path: "/docs/report.txt" }),
      },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      2,
      "mounts/mount-1/duplicate/",
      {
        method: "POST",
        params: { path: "/docs/report.txt" },
      },
      { redirectOn40x: false },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      3,
      "mounts/mount-1/folders/",
      {
        method: "POST",
        params: { path: "/docs" },
        body: JSON.stringify({
          name: "reports",
          reuse_existing: true,
        }),
      },
      { redirectOn40x: false },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      4,
      "mounts/mount-1/rename/",
      {
        method: "POST",
        params: { path: "/docs/report.txt" },
        body: JSON.stringify({ name: "report-renamed.txt" }),
      },
      { redirectOn40x: false },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      5,
      "mounts/mount-1/move/",
      {
        method: "POST",
        params: { path: "/docs/report.txt" },
        body: JSON.stringify({ target_path: "/archive" }),
      },
      { redirectOn40x: false },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      6,
      "mounts/mount-1/delete/",
      {
        method: "DELETE",
        params: { path: "/docs/report.txt" },
      },
      { redirectOn40x: false },
    );
  });
});
