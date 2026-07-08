import { UploadError } from "@/features/errors/UploadError";
import { uploadFile } from "../StandardDriver";
import { FakeXMLHttpRequest } from "./fakeXhr";

jest.mock("@/features/i18n/initI18n", () => ({
  __esModule: true,
  default: {
    t: (key: string) => `translated:${key}`,
  },
}));

describe("uploadFile", () => {
  const originalXMLHttpRequest = global.XMLHttpRequest;

  beforeEach(() => {
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

  it("configures the XHR runtime, reports progress and resolves on 200", async () => {
    const progressHandler = jest.fn();
    FakeXMLHttpRequest.enqueue({
      onSend: (xhr) => {
        xhr.emitUploadProgress(25, 100);
        xhr.complete({ status: 200 });
      },
    });

    await expect(
      uploadFile(
        "https://upload.example.test/policy",
        { type: "text/plain" } as File,
        progressHandler,
        321,
      ).promise,
    ).resolves.toBe(true);

    const xhr = FakeXMLHttpRequest.instances[0];
    expect(xhr?.method).toBe("PUT");
    expect(xhr?.url).toBe("https://upload.example.test/policy");
    expect(xhr?.headers).toEqual({
      "X-amz-acl": "private",
      "Content-Type": "text/plain",
    });
    expect(xhr?.timeout).toBe(321);
    expect(progressHandler.mock.calls).toEqual([[25], [100]]);
  });

  it("maps 400/403 upload failures to a reinitiate UploadError", async () => {
    FakeXMLHttpRequest.enqueue({
      onSend: (xhr) => {
        xhr.complete({ status: 403 });
      },
    });

    await expect(
      uploadFile(
        "https://upload.example.test/policy",
        { type: "text/plain" } as File,
        jest.fn(),
      ).promise,
    ).rejects.toMatchObject({
      message: "translated:explorer.actions.upload.errors.policy_expired",
      kind: "put_failed",
      nextAction: "reinitiate",
    });
  });

  it("maps timeout events to a retryable UploadError with itemId context", async () => {
    FakeXMLHttpRequest.enqueue({
      onSend: (xhr) => {
        xhr.emit("timeout");
      },
    });

    await expect(
      uploadFile(
        "https://upload.example.test/policy",
        { type: "text/plain" } as File,
        jest.fn(),
        123,
        { itemId: "item-1" },
      ).promise,
    ).rejects.toMatchObject({
      message: "translated:explorer.actions.upload.errors.timeout",
      kind: "timeout",
      nextAction: "retry",
      itemId: "item-1",
    });
  });

  it("maps 5xx and generic failures to retryable UploadError variants", async () => {
    FakeXMLHttpRequest.enqueue({
      onSend: (xhr) => {
        xhr.complete({ status: 503 });
      },
    });
    await expect(
      uploadFile(
        "https://upload.example.test/policy",
        { type: "text/plain" } as File,
        jest.fn(),
      ).promise,
    ).rejects.toMatchObject({
      message: "translated:explorer.actions.upload.errors.storage_unavailable",
      kind: "put_failed",
      nextAction: "retry",
    });

    FakeXMLHttpRequest.enqueue({
      onSend: (xhr) => {
        xhr.complete({ status: 418 });
      },
    });
    await expect(
      uploadFile(
        "https://upload.example.test/policy",
        { type: "text/plain" } as File,
        jest.fn(),
      ).promise,
    ).rejects.toMatchObject({
      message: "translated:explorer.actions.upload.errors.put_failed",
      kind: "put_failed",
      nextAction: "retry",
    });

    FakeXMLHttpRequest.enqueue({
      onSend: (xhr) => {
        xhr.emit("error");
      },
    });
    await expect(
      uploadFile(
        "https://upload.example.test/policy",
        { type: "text/plain" } as File,
        jest.fn(),
      ).promise,
    ).rejects.toBeInstanceOf(UploadError);
  });

  it("rejects aborts as AbortError instead of retryable upload failures", async () => {
    FakeXMLHttpRequest.enqueue({});

    const upload = uploadFile(
      "https://upload.example.test/policy",
      { type: "text/plain" } as File,
      jest.fn(),
    );

    upload.abort();

    await expect(upload.promise).rejects.toMatchObject({
      name: "AbortError",
    });
  });
});
