import { APIError } from "@/features/api/APIError";
import { AppError } from "@/features/errors/AppError";
import { StandardDriver } from "../StandardDriver";
import { ensureCsrfCookie, getCSRFToken } from "@/features/api/fetchApi";
import { baseApiUrl, isJson } from "@/features/api/utils";
import { FakeXMLHttpRequest } from "./fakeXhr";

jest.mock("@/features/api/fetchApi", () => ({
  ensureCsrfCookie: jest.fn(),
  fetchAPI: jest.fn(),
  getCSRFToken: jest.fn(),
}));

jest.mock("@/features/api/utils", () => ({
  baseApiUrl: jest.fn(),
  isJson: jest.fn(),
}));

jest.mock("@/features/i18n/initI18n", () => ({
  __esModule: true,
  default: {
    t: (key: string) => `translated:${key}`,
  },
}));

const mockedEnsureCsrfCookie = jest.mocked(ensureCsrfCookie);
const mockedGetCSRFToken = jest.mocked(getCSRFToken);
const mockedBaseApiUrl = jest.mocked(baseApiUrl);
const mockedIsJson = jest.mocked(isJson);

describe("StandardDriver mount upload runtime", () => {
  const originalXMLHttpRequest = global.XMLHttpRequest;
  let driver: StandardDriver;

  beforeEach(() => {
    driver = new StandardDriver();
    FakeXMLHttpRequest.reset();
    mockedEnsureCsrfCookie.mockReset();
    mockedGetCSRFToken.mockReset();
    mockedBaseApiUrl.mockReset();
    mockedIsJson.mockReset();
    mockedBaseApiUrl.mockReturnValue("http://api.example.test/api/v1.0/");
    mockedIsJson.mockImplementation((value: string) => value.trim().startsWith("{"));
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

  it("keeps uploadMountFile on the canonical CSRF/FormData/progress success flow", async () => {
    const file = new File(["hello"], "report.txt", { type: "text/plain" });
    const progressHandler = jest.fn();
    mockedGetCSRFToken.mockReturnValue("csrf-123");
    FakeXMLHttpRequest.enqueue({
      onSend: (xhr) => {
        xhr.emitUploadProgress(40, 100);
        xhr.complete({
          status: 201,
          responseText: JSON.stringify({
            mount_id: "mount-1",
            normalized_path: "/docs/report.txt",
          }),
        });
      },
    });

    const uploaded = await driver.uploadMountFile({
      mountId: "mount-1",
      path: "/docs",
      file,
      progressHandler,
    });

    expect(mockedBaseApiUrl).toHaveBeenCalledWith("1.0");
    expect(mockedEnsureCsrfCookie).not.toHaveBeenCalled();
    const xhr = FakeXMLHttpRequest.instances[0];
    expect(xhr?.method).toBe("POST");
    expect(xhr?.url).toBe(
      "http://api.example.test/api/v1.0/mounts/mount-1/upload/?path=%2Fdocs",
    );
    expect(xhr?.withCredentials).toBe(true);
    expect(xhr?.headers).toEqual({ "X-CSRFToken": "csrf-123" });
    expect(xhr?.sentBody).toBeInstanceOf(FormData);
    const uploadedFile = (xhr?.sentBody as FormData).get("file") as File;
    expect(uploadedFile.name).toBe("report.txt");
    expect(uploadedFile.type).toBe("text/plain");
    expect(progressHandler.mock.calls).toEqual([[40], [100]]);
    expect(uploaded).toEqual({
      mount_id: "mount-1",
      normalized_path: "/docs/report.txt",
    });
  });

  it("bootstraps CSRF when missing before sending the upload", async () => {
    mockedGetCSRFToken
      .mockReturnValueOnce(null)
      .mockReturnValueOnce("csrf-bootstrapped");
    FakeXMLHttpRequest.enqueue({
      onSend: (xhr) => {
        xhr.complete({
          status: 200,
          responseText: JSON.stringify({
            mount_id: "mount-1",
            normalized_path: "/docs/report.txt",
          }),
        });
      },
    });

    await driver.uploadMountFile({
      mountId: "mount-1",
      path: "/docs",
      file: new File(["hello"], "report.txt", { type: "text/plain" }),
    });

    expect(mockedEnsureCsrfCookie).toHaveBeenCalledTimes(1);
    expect(FakeXMLHttpRequest.instances[0]?.headers).toEqual({
      "X-CSRFToken": "csrf-bootstrapped",
    });
  });

  it("fails closed with AppError when mount upload succeeds without JSON body", async () => {
    mockedGetCSRFToken.mockReturnValue("csrf-123");
    FakeXMLHttpRequest.enqueue({
      onSend: (xhr) => {
        xhr.complete({ status: 201, responseText: "" });
      },
    });

    await expect(
      driver.uploadMountFile({
        mountId: "mount-1",
        path: "/docs",
        file: new File(["hello"], "report.txt", { type: "text/plain" }),
      }),
    ).rejects.toEqual(new AppError("translated:api.error.unexpected"));
  });

  it("maps JSON and non-JSON mount upload failures to the current APIError contract", async () => {
    mockedGetCSRFToken.mockReturnValue("csrf-123");
    FakeXMLHttpRequest.enqueue({
      onSend: (xhr) => {
        xhr.complete({
          status: 409,
          responseText: JSON.stringify({ detail: "conflict" }),
        });
      },
    });
    await expect(
      driver.uploadMountFile({
        mountId: "mount-1",
        path: "/docs",
        file: new File(["hello"], "report.txt", { type: "text/plain" }),
      }),
    ).rejects.toMatchObject({
      code: 409,
      data: { detail: "conflict" },
    });

    FakeXMLHttpRequest.enqueue({
      onSend: (xhr) => {
        xhr.complete({
          status: 500,
          responseText: "internal error",
        });
      },
    });
    await expect(
      driver.uploadMountFile({
        mountId: "mount-1",
        path: "/docs",
        file: new File(["hello"], "report.txt", { type: "text/plain" }),
      }),
    ).rejects.toEqual(new APIError(500));
  });

  it("maps low-level error and abort events to AppError", async () => {
    mockedGetCSRFToken.mockReturnValue("csrf-123");
    FakeXMLHttpRequest.enqueue({
      onSend: (xhr) => {
        xhr.emit("error");
      },
    });

    await expect(
      driver.uploadMountFile({
        mountId: "mount-1",
        path: "/docs",
        file: new File(["hello"], "report.txt", { type: "text/plain" }),
      }),
    ).rejects.toEqual(new AppError("translated:api.error.unexpected"));
  });
});
