import { getDriver } from "@/features/config/Config";

import {
  defaultPreviewSource,
  getResolvePreviewQueryKey,
  getTextPreviewQueryKey,
  type FilePreviewType,
  type PreviewSource,
} from "../previewSource";

jest.mock("@/features/config/Config", () => ({
  getDriver: jest.fn(),
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
}));

const mockedGetDriver = jest.mocked(getDriver);
const { APIError } = jest.requireMock("@/features/api/APIError") as {
  APIError: new (code: number, data?: unknown) => Error;
};

const buildFile = (
  overrides: Partial<FilePreviewType> = {},
): FilePreviewType => ({
  id: "file-1",
  size: 128,
  title: "Report",
  filename: "Report.txt",
  mimetype: "text/plain",
  ...overrides,
});

describe("previewSource", () => {
  const getItemText = jest.fn();
  const saveItemText = jest.fn();

  beforeEach(() => {
    getItemText.mockReset();
    saveItemText.mockReset();
    mockedGetDriver.mockReturnValue({
      getItemText,
      saveItemText,
    } as never);
  });

  it("forwards text preview fetches to the default driver source", async () => {
    const content = {
      content: "hello",
      truncated: false,
      size: 5,
      max_preview_bytes: 1024,
      etag: "etag-1",
    };
    getItemText.mockResolvedValue(content);

    await expect(defaultPreviewSource.fetchTextContent?.(buildFile())).resolves.toEqual(
      content,
    );
    expect(getItemText).toHaveBeenCalledWith("file-1");
  });

  it("maps APIError 400 and 415 to a null text preview response", async () => {
    getItemText.mockRejectedValueOnce(new APIError(400));
    await expect(defaultPreviewSource.fetchTextContent?.(buildFile())).resolves.toBeNull();

    getItemText.mockRejectedValueOnce(new APIError(415));
    await expect(defaultPreviewSource.fetchTextContent?.(buildFile())).resolves.toBeNull();
  });

  it("propagates non-ignored preview fetch errors", async () => {
    const apiError = new APIError(500);
    const genericError = new Error("boom");
    getItemText.mockRejectedValueOnce(apiError);
    await expect(defaultPreviewSource.fetchTextContent?.(buildFile())).rejects.toBe(
      apiError,
    );

    getItemText.mockRejectedValueOnce(genericError);
    await expect(defaultPreviewSource.fetchTextContent?.(buildFile())).rejects.toBe(
      genericError,
    );
  });

  it("forwards text save requests to the default driver source", async () => {
    saveItemText.mockResolvedValue({ etag: "etag-2" });

    await expect(
      defaultPreviewSource.saveTextContent?.({
        file: buildFile({ id: "file-9" }),
        content: "updated",
        etag: "etag-1",
      }),
    ).resolves.toEqual({ etag: "etag-2" });

    expect(saveItemText).toHaveBeenCalledWith({
      itemId: "file-9",
      content: "updated",
      etag: "etag-1",
    });
  });

  it("keeps default query keys stable for text and resolved preview", () => {
    const file = buildFile({ id: "file-2" });

    expect(getTextPreviewQueryKey(defaultPreviewSource, file)).toEqual([
      "item",
      "file-2",
      "text",
    ]);
    expect(getResolvePreviewQueryKey(defaultPreviewSource, file)).toEqual([
      "file-preview",
      "file-2",
      "resolved",
    ]);
  });

  it("honors custom preview source query key overrides", () => {
    const source: PreviewSource = {
      getTextQueryKey: (file) => ["custom-text", file.id, "v2"],
      getResolveFilePreviewQueryKey: (file) => [
        "custom-resolve",
        file.id,
        "v2",
      ],
    };
    const file = buildFile({ id: "file-3" });

    expect(getTextPreviewQueryKey(source, file)).toEqual([
      "custom-text",
      "file-3",
      "v2",
    ]);
    expect(getResolvePreviewQueryKey(source, file)).toEqual([
      "custom-resolve",
      "file-3",
      "v2",
    ]);
  });
});
