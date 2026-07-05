import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MimeCategory } from "@/features/explorer/utils/mimeTypes";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import type { FilePreviewType, PreviewSource } from "../previewSource";
import { useResolvedPreviewFile } from "../useResolvedPreviewFile";

jest.mock("@tanstack/react-query", () => ({
  useQuery: jest.fn(),
  useQueryClient: jest.fn(),
}));

const mockedUseQuery = jest.mocked(useQuery);
const mockedUseQueryClient = jest.mocked(useQueryClient);

type PreviewFileWithCategory = FilePreviewType & {
  category: MimeCategory;
};

const buildFile = (
  overrides: Partial<PreviewFileWithCategory> = {},
): PreviewFileWithCategory => ({
  id: "file-1",
  size: 128,
  title: "Report",
  filename: "Report.bin",
  mimetype: "application/octet-stream",
  category: MimeCategory.OTHER,
  ...overrides,
});

describe("useResolvedPreviewFile", () => {
  let controller:
    | ReturnType<typeof useResolvedPreviewFile<PreviewFileWithCategory>>
    | undefined;

  const renderHarness = (
    currentFile: PreviewFileWithCategory | undefined,
    source: PreviewSource,
  ) => {
    const Harness = () => {
      controller = useResolvedPreviewFile(currentFile, source);
      return null;
    };

    renderToStaticMarkup(<Harness />);
    return controller;
  };

  beforeEach(() => {
    controller = undefined;
    jest.useFakeTimers().setSystemTime(new Date("2026-03-31T12:00:00Z"));
    mockedUseQuery.mockReset();
    mockedUseQueryClient.mockReset();
    mockedUseQuery.mockImplementation(
      (config) =>
        ({
          data: null,
          isLoading: false,
          ...config,
        }) as never,
    );
    mockedUseQueryClient.mockReturnValue({
      getQueryData: jest.fn(() => undefined),
    } as never);
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("reuses a fresh cached resolved stream and skips the resolve query", () => {
    const currentFile = buildFile({
      category: MimeCategory.OTHER,
      mimetype: "application/octet-stream",
    });
    const getQueryData = jest.fn(() => ({
      stream_url: "https://stream.example.test/file",
      stream_expires_at: Date.now() + 60_000,
      preview_kind: "audio",
    }));
    mockedUseQueryClient.mockReturnValue({
      getQueryData,
    } as never);

    const result = renderHarness(currentFile, {
      resolveFilePreview: jest.fn(),
    });

    expect(mockedUseQuery.mock.calls[0][0]).toEqual(
      expect.objectContaining({
        queryKey: ["file-preview", "file-1", "resolved"],
        enabled: false,
        refetchOnWindowFocus: false,
        retry: false,
      }),
    );
    expect(result?.effectiveCurrentFile).toMatchObject({
      stream_url: "https://stream.example.test/file",
      preview_kind: "audio",
      category: MimeCategory.AUDIO,
    });
    expect(result?.isResolvingCurrentFile).toBe(false);
  });

  it("keeps the fallback unresolved query key when there is no current file", () => {
    const result = renderHarness(undefined, {});

    expect(mockedUseQuery.mock.calls[0][0]).toEqual(
      expect.objectContaining({
        queryKey: ["file-preview", undefined, "resolved"],
        enabled: false,
      }),
    );
    expect(result?.effectiveCurrentFile).toBeUndefined();
    expect(result?.isResolvingCurrentFile).toBe(false);
  });

  it("enables the resolve query only when a file and resolver are both present", async () => {
    const currentFile = buildFile({ id: "file-2" });
    const resolveFilePreview = jest.fn().mockResolvedValue({
      stream_url: "https://stream.example.test/2",
      preview_kind: "pdf",
    });
    mockedUseQuery.mockImplementation((config) => config as never);

    renderHarness(currentFile, {
      resolveFilePreview,
      getResolveFilePreviewQueryKey: (file) => ["custom-resolve", file.id],
    });

    const queryConfig = mockedUseQuery.mock.calls[0][0] as {
      queryKey: string[];
      enabled: boolean;
      queryFn: () => Promise<unknown>;
    };

    expect(queryConfig.queryKey).toEqual(["custom-resolve", "file-2"]);
    expect(queryConfig.enabled).toBe(true);
    await expect(queryConfig.queryFn()).resolves.toEqual({
      stream_url: "https://stream.example.test/2",
      preview_kind: "pdf",
    });
    expect(resolveFilePreview).toHaveBeenCalledWith(currentFile);
  });

  it("merges resolved data into the effective file and derives archive category from filename fallback", () => {
    const currentFile = buildFile({
      id: "file-3",
      filename: "backup.zip",
      title: "backup.zip",
      mimetype: "application/octet-stream",
      category: MimeCategory.OTHER,
    });
    mockedUseQuery.mockImplementation(
      () =>
        ({
          data: {
            filename: "backup.zip",
            mimetype: "application/octet-stream",
          },
          isLoading: false,
        }) as never,
    );

    const result = renderHarness(currentFile, {
      resolveFilePreview: jest.fn(),
    });

    expect(result?.effectiveCurrentFile).toMatchObject({
      id: "file-3",
      filename: "backup.zip",
      category: MimeCategory.ARCHIVE,
    });
  });

  it("forces explicit preview kinds to the expected categories and exposes the resolving state", () => {
    const currentFile = buildFile({
      id: "file-4",
      filename: "clip.bin",
      category: MimeCategory.OTHER,
    });
    mockedUseQuery.mockImplementation(
      () =>
        ({
          data: undefined,
          isLoading: true,
        }) as never,
    );

    const loadingResult = renderHarness(currentFile, {
      resolveFilePreview: jest.fn(),
    });
    expect(loadingResult?.isResolvingCurrentFile).toBe(true);

    mockedUseQuery.mockImplementation(
      () =>
        ({
          data: {
            preview_kind: "video",
          },
          isLoading: false,
        }) as never,
    );

    const resolvedResult = renderHarness(currentFile, {
      resolveFilePreview: jest.fn(),
    });

    expect(resolvedResult?.effectiveCurrentFile).toMatchObject({
      preview_kind: "video",
      category: MimeCategory.VIDEO,
    });
    expect(resolvedResult?.isResolvingCurrentFile).toBe(false);
  });
});
