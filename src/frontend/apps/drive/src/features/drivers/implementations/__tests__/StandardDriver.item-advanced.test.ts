import { StandardDriver } from "../StandardDriver";
import { fetchAPI } from "@/features/api/fetchApi";
import { getRuntimeConfig } from "@/features/config/runtimeConfig";
import { AppError } from "@/features/errors/AppError";
import { getOperationTimeBound } from "@/features/operations/timeBounds";
import { FakeXMLHttpRequest } from "./fakeXhr";

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

jest.mock("@/features/i18n/initI18n", () => ({
  __esModule: true,
  default: {
    t: (key: string) => `translated:${key}`,
  },
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

const buildItemJson = (overrides: Record<string, unknown> = {}) => ({
  id: "item-1",
  title: "Quarterly report",
  filename: "Quarterly report.pdf",
  creator: {
    id: "user-1",
    full_name: "Jane Doe",
    short_name: "JD",
  },
  type: "file",
  ancestors_link_reach: null,
  ancestors_link_role: null,
  computed_link_reach: null,
  computed_link_role: null,
  upload_state: "ready",
  updated_at: "2026-03-31T08:00:00.000Z",
  description: "",
  created_at: "2026-03-30T08:00:00.000Z",
  path: "/Quarterly report.pdf",
  mimetype: "application/pdf",
  link_reach: "restricted",
  link_role: "reader",
  abilities: {
    accesses_manage: false,
    accesses_view: true,
    children_create: false,
    children_list: false,
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
    partial_update: false,
    restore: false,
    retrieve: true,
    tree: false,
    update: false,
    upload_ended: false,
  },
  ...overrides,
});

describe("StandardDriver item-side advanced adapters", () => {
  const originalXMLHttpRequest = global.XMLHttpRequest;
  let driver: StandardDriver;

  beforeEach(() => {
    driver = new StandardDriver();
    mockedFetchAPI.mockReset();
    mockedGetRuntimeConfig.mockReset();
    mockedGetOperationTimeBound.mockReset();
    mockedGetRuntimeConfig.mockReturnValue({ some: "config" } as never);
    mockedGetOperationTimeBound.mockImplementation((operation: string) => {
      const bounds: Record<string, { fail_ms: number; still_working_ms: number }> = {
        config_load: { still_working_ms: 10, fail_ms: 101 },
        upload_create: { still_working_ms: 20, fail_ms: 202 },
        upload_put: { still_working_ms: 30, fail_ms: 303 },
        upload_finalize: { still_working_ms: 40, fail_ms: 404 },
        wopi_info: { still_working_ms: 50, fail_ms: 505 },
      };
      return bounds[operation];
    });
    FakeXMLHttpRequest.reset();
    Object.defineProperty(global, "XMLHttpRequest", {
      configurable: true,
      value: FakeXMLHttpRequest,
    });
  });

  afterEach(() => {
    Object.defineProperty(global, "XMLHttpRequest", {
      configurable: true,
      value: originalXMLHttpRequest,
    });
  });

  it("keeps getConfig and getWopiInfo on their timeout-bound endpoints", async () => {
    const config = { FRONTEND_THEME: "custom" };
    const wopiInfo = {
      access_token: "token",
      access_token_ttl: 3600,
      launch_url: "https://office.example.test",
    };
    mockedFetchAPI
      .mockResolvedValueOnce(makeResponse(config))
      .mockResolvedValueOnce(makeResponse(wopiInfo));

    await expect(driver.getConfig()).resolves.toEqual(config);
    await expect(driver.getWopiInfo("item-1")).resolves.toEqual(wopiInfo);

    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      1,
      "config/",
      undefined,
      { timeoutMs: 101 },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      2,
      "items/item-1/wopi/",
      undefined,
      { timeoutMs: 505 },
    );
  });

  it("keeps getItemText on the text endpoint and resolves ETag from the header first", async () => {
    mockedFetchAPI.mockResolvedValueOnce(
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
    );

    await expect(driver.getItemText("item-1")).resolves.toEqual({
      content: "hello",
      truncated: false,
      size: 5,
      max_preview_bytes: 100,
      etag: "header-etag",
    });

    expect(mockedFetchAPI).toHaveBeenCalledWith(
      "items/item-1/text/",
      undefined,
      { redirectOn40x: false },
    );
  });

  it("keeps saveItemText headers/body and resolves ETag from header, body or null", async () => {
    mockedFetchAPI
      .mockResolvedValueOnce(
        makeResponse({ etag: "body-etag" }, { headerEtag: "header-etag" }),
      )
      .mockResolvedValueOnce(makeResponse({ etag: "body-only-etag" }))
      .mockResolvedValueOnce(
        makeResponse(
          {},
          { headerEtag: null, jsonError: new Error("no body") },
        ),
      );

    await expect(
      driver.saveItemText({
        itemId: "item-1",
        content: "hello",
        etag: "if-match-etag",
      }),
    ).resolves.toEqual({ etag: "header-etag" });

    await expect(
      driver.saveItemText({
        itemId: "item-1",
        content: "world",
        etag: "if-match-etag-2",
      }),
    ).resolves.toEqual({ etag: "body-only-etag" });

    await expect(
      driver.saveItemText({
        itemId: "item-1",
        content: "fallback",
        etag: "if-match-etag-3",
      }),
    ).resolves.toEqual({ etag: null });

    expect(mockedFetchAPI).toHaveBeenNthCalledWith(1, "items/item-1/text/", {
      method: "PUT",
      headers: { "If-Match": "if-match-etag" },
      body: JSON.stringify({ content: "hello" }),
    });
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(2, "items/item-1/text/", {
      method: "PUT",
      headers: { "If-Match": "if-match-etag-2" },
      body: JSON.stringify({ content: "world" }),
    });
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(3, "items/item-1/text/", {
      method: "PUT",
      headers: { "If-Match": "if-match-etag-3" },
      body: JSON.stringify({ content: "fallback" }),
    });
  });

  it("keeps createFile on the policy -> upload -> upload-ended flow with a proxied progress handler", async () => {
    const file = { type: "application/pdf" } as File;
    const progressHandler = jest.fn();
    FakeXMLHttpRequest.enqueue({
      onSend: (xhr) => {
        xhr.emitUploadProgress(50, 100);
        xhr.complete({ status: 200 });
      },
    });
    mockedFetchAPI
      .mockResolvedValueOnce(
        makeResponse(
          buildItemJson({
            id: "item-created",
            policy: "https://upload.example.test/policy",
          }),
        ),
      )
      .mockResolvedValueOnce(makeResponse({}, { status: 204 }));

    const created = await driver.createFile({
      parentId: "parent-1",
      file,
      filename: "Quarterly report.pdf",
      progressHandler,
    });

    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      1,
      "items/parent-1/children/",
      {
        method: "POST",
        body: JSON.stringify({
          type: "file",
          filename: "Quarterly report.pdf",
        }),
      },
      {
        redirectOn40x: false,
        timeoutMs: 202,
      },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      2,
      "items/item-created/upload-ended/",
      { method: "POST" },
      { redirectOn40x: false, timeoutMs: 404 },
    );
    expect(progressHandler.mock.calls).toEqual([[45], [90], [100]]);
    expect(created.updated_at).toBeInstanceOf(Date);
  });

  it("keeps createFile fail-closed on missing policy and finalize failures", async () => {
    const file = { type: "application/pdf" } as File;
    mockedFetchAPI.mockResolvedValueOnce(makeResponse(buildItemJson()));

    await expect(
      driver.createFile({
        file,
        filename: "Quarterly report.pdf",
      }),
    ).rejects.toEqual(new AppError("translated:api.error.unexpected"));

    FakeXMLHttpRequest.enqueue({
      onSend: (xhr) => {
        xhr.complete({ status: 200 });
      },
    });
    mockedFetchAPI
      .mockReset()
      .mockResolvedValueOnce(
        makeResponse(
          buildItemJson({
            id: "item-created",
            policy: "https://upload.example.test/policy",
          }),
        ),
      )
      .mockRejectedValueOnce(new Error("finalize failed"));

    await expect(
      driver.createFile({
        file,
        filename: "Quarterly report.pdf",
      }),
    ).rejects.toMatchObject({
      message: "translated:explorer.actions.upload.errors.finalize_failed",
      kind: "finalize_failed",
      nextAction: "retry",
      itemId: "item-created",
    });
  });

  it("keeps reinitiateFileUpload on the upload-policy -> upload-ended flow and suppresses upload 100", async () => {
    const file = { type: "application/pdf" } as File;
    const progressHandler = jest.fn();
    FakeXMLHttpRequest.enqueue({
      onSend: (xhr) => {
        xhr.emitUploadProgress(40, 100);
        xhr.complete({ status: 200 });
      },
    });
    mockedFetchAPI
      .mockResolvedValueOnce(
        makeResponse({
          policy: "https://upload.example.test/reinitiate",
        }),
      )
      .mockResolvedValueOnce(makeResponse({}, { status: 204 }));

    await expect(
      driver.reinitiateFileUpload({
        itemId: "item-1",
        file,
        filename: "Quarterly report.pdf",
        progressHandler,
      }),
    ).resolves.toBeUndefined();

    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      1,
      "items/item-1/upload-policy/",
      { method: "POST" },
      { redirectOn40x: false, timeoutMs: 202 },
    );
    expect(mockedFetchAPI).toHaveBeenNthCalledWith(
      2,
      "items/item-1/upload-ended/",
      { method: "POST" },
      { redirectOn40x: false, timeoutMs: 404 },
    );
    expect(progressHandler.mock.calls).toEqual([[40], [100]]);
  });

  it("keeps reinitiateFileUpload fail-closed when upload policy creation fails", async () => {
    mockedFetchAPI.mockRejectedValueOnce(new Error("create failed"));

    await expect(
      driver.reinitiateFileUpload({
        itemId: "item-1",
        file: { type: "application/pdf" } as File,
        filename: "Quarterly report.pdf",
      }),
    ).rejects.toMatchObject({
      message: "translated:explorer.actions.upload.errors.reinitiate_failed",
      kind: "create_failed",
      nextAction: "contact_admin",
      itemId: "item-1",
    });
  });
});
