import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import posthog from "posthog-js";
import { MimeCategory } from "@/features/explorer/utils/mimeTypes";
import { FilePreview, getPdfPreviewSrc } from "../FilesPreview";
import type { FilePreviewType, PreviewSource } from "../previewSource";
import { useResolvedPreviewFile } from "../useResolvedPreviewFile";

const renderedButtons: Array<{
  children?: React.ReactNode;
  onClick?: () => void;
  icon?: React.ReactElement<{ name?: string }>;
  ["data-testid"]?: string;
}> = [];

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
  initReactI18next: {
    type: "3rdParty",
    init: jest.fn(),
  },
}));

jest.mock("@tanstack/react-query", () => ({
  useQuery: jest.fn(),
  useMutation: jest.fn(),
  useQueryClient: jest.fn(),
}));

jest.mock("posthog-js", () => ({
  capture: jest.fn(),
}));

jest.mock("react-toastify", () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
    info: jest.fn(),
  },
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  Icon: ({ name }: { name: string }) => <span>{name}</span>,
  IconType: {
    OUTLINED: "outlined",
  },
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: {
    children?: React.ReactNode;
    onClick?: () => void;
    icon?: React.ReactElement<{ name?: string }>;
    ["data-testid"]?: string;
  }) => {
    renderedButtons.push(props);
    return <button>{props.children ?? props.icon}</button>;
  },
  Modal: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  ModalSize: {
    FULL: "full",
  },
  Tooltip: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock("../useResolvedPreviewFile", () => ({
  useResolvedPreviewFile: jest.fn(),
}));

jest.mock("../../image-viewer/ImageViewer", () => ({
  ImageViewer: ({ src }: { src: string }) => <div>image-viewer:{src}</div>,
}));

jest.mock("../../video-player/VideoPlayer", () => ({
  VideoPlayer: ({ src }: { src: string }) => <div>video-player:{src}</div>,
}));

jest.mock("../../audio-player/AudioPlayer", () => ({
  AudioPlayer: ({ src }: { src: string }) => <div>audio-player:{src}</div>,
}));

jest.mock("../../pdf-preview/PreviewPdf", () => ({
  PreviewPdf: ({ src }: { src: string }) => <div>pdf-preview:{src}</div>,
}));

jest.mock("../../archive-viewer/ArchiveViewer", () => ({
  ArchiveViewer: ({ archiveDetailsItemId }: { archiveDetailsItemId: string }) => (
    <div>archive-viewer:{archiveDetailsItemId}</div>
  ),
}));

jest.mock("../../not-supported/NotSupportedPreview", () => ({
  NotSupportedPreview: ({ title }: { title?: string }) => (
    <div>not-supported:{title ?? "default"}</div>
  ),
}));

jest.mock("../../suspicious/SuspiciousPreview", () => ({
  SuspiciousPreview: () => <div>suspicious-preview</div>,
}));

jest.mock("../../wopi/WopiEditor", () => ({
  WopiEditor: ({ item }: { item: { id: string } }) => <div>wopi-editor:{item.id}</div>,
}));

jest.mock("../../text-preview/TextPreview", () => ({
  TextPreview: ({ filename }: { filename: string }) => <div>text-preview:{filename}</div>,
}));

jest.mock("@/features/explorer/components/icons/ItemIcon", () => ({
  FileIcon: ({ file }: { file: { id: string } }) => <span>file-icon:{file.id}</span>,
}));

const mockedUseQuery = jest.mocked(useQuery);
const mockedUseMutation = jest.mocked(useMutation);
const mockedUseQueryClient = jest.mocked(useQueryClient);
const mockedUseResolvedPreviewFile = jest.mocked(useResolvedPreviewFile);
const mockedPosthog = jest.mocked(posthog);

const buildPreviewFile = (
  overrides: Partial<FilePreviewType> & { category?: MimeCategory } = {},
) =>
  ({
    id: "file-1",
    size: 128,
    title: "Demo",
    filename: "Demo.png",
    mimetype: "image/png",
    url_preview: "https://example.test/preview.png",
    url: "https://example.test/file",
    category: MimeCategory.IMAGE,
    ...overrides,
  }) as FilePreviewType & { category: MimeCategory };

describe("FilePreview", () => {
  const realUseState = React.useState;
  let useStateSpy: jest.SpiedFunction<typeof React.useState> | undefined;

  beforeEach(() => {
    renderedButtons.length = 0;
    mockedUseQuery.mockReset();
    mockedUseMutation.mockReset();
    mockedUseQueryClient.mockReset();
    mockedUseResolvedPreviewFile.mockReset();
    mockedPosthog.capture.mockReset();

    mockedUseQueryClient.mockReturnValue({
      setQueryData: jest.fn(),
    } as never);
    mockedUseQuery.mockReturnValue({
      data: null,
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as never);
    mockedUseMutation.mockReturnValue({
      mutate: jest.fn(),
      isPending: false,
    } as never);
  });

  afterEach(() => {
    useStateSpy?.mockRestore();
  });

  it("keeps the generic preview chrome and image viewer wiring intact", () => {
    const setCurrentIndex = jest.fn();
    const setIsSidebarOpen = jest.fn();
    const imageFile = buildPreviewFile();
    const siblingImage = buildPreviewFile({
      id: "file-2",
      title: "Second",
      filename: "Second.png",
    });
    const handleDownloadFile = jest.fn();

    useStateSpy = jest
      .spyOn(React, "useState")
      .mockImplementation(realUseState as never)
      .mockImplementationOnce((() => [0, setCurrentIndex]) as never)
      .mockImplementationOnce((() => [false, setIsSidebarOpen]) as never);

    mockedUseResolvedPreviewFile.mockReturnValue({
      effectiveCurrentFile: imageFile,
      isResolvingCurrentFile: false,
      resolvedPreviewQuery: {
        isError: false,
        error: null,
        refetch: jest.fn(),
      },
    } as never);

    const html = renderToStaticMarkup(
      <FilePreview
        isOpen={true}
        files={[imageFile, siblingImage]}
        headerRightContent={<div>header-extra</div>}
        sidebarContent={<div>sidebar-extra</div>}
        handleDownloadFile={handleDownloadFile}
      />,
    );

    const downloadButton = renderedButtons.find(
      (button) => button.icon?.props.name === "file_download",
    );
    const sidebarButton = renderedButtons.find(
      (button) => button.icon?.props.name === "info_outline",
    );
    const nextButton = renderedButtons.find(
      (button) => button.icon?.props.name === "arrow_forward",
    );

    downloadButton?.onClick?.();
    sidebarButton?.onClick?.();
    nextButton?.onClick?.();

    expect(html).toContain("image-viewer:https://example.test/preview.png");
    expect(html).toContain("data-testid=\"file-preview-nav\"");
    expect(html).toContain("header-extra");
    expect(html).toContain("sidebar-extra");
    expect(handleDownloadFile).toHaveBeenCalledWith(imageFile);
    expect(setIsSidebarOpen).toHaveBeenCalledWith(true);
    expect(setCurrentIndex).toHaveBeenCalledWith(1);
  });

  it("keeps text preview header actions wired for editable text content", () => {
    const setIsEditingText = jest.fn();
    const textFile = buildPreviewFile({
      id: "text-1",
      title: "Notes",
      filename: "Notes.txt",
      mimetype: "text/plain",
      category: MimeCategory.OTHER,
      preview_kind: "text",
      is_wopi_supported: false,
    });

    useStateSpy = jest
      .spyOn(React, "useState")
      .mockImplementation(realUseState as never)
      .mockImplementationOnce((() => [0, jest.fn()]) as never)
      .mockImplementationOnce((() => [false, jest.fn()]) as never)
      .mockImplementationOnce((() => [false, setIsEditingText]) as never)
      .mockImplementationOnce((() => ["hello", jest.fn()]) as never)
      .mockImplementationOnce((() => ["hello", jest.fn()]) as never)
      .mockImplementationOnce((() => ["etag-1", jest.fn()]) as never)
      .mockImplementationOnce((() => [false, jest.fn()]) as never);

    mockedUseResolvedPreviewFile.mockReturnValue({
      effectiveCurrentFile: textFile,
      isResolvingCurrentFile: false,
      resolvedPreviewQuery: {
        isError: false,
        error: null,
        refetch: jest.fn(),
      },
    } as never);
    mockedUseQuery.mockReturnValue({
      data: {
        content: "hello",
        etag: "etag-1",
        read_only: false,
        truncated: false,
      },
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    } as never);

    const html = renderToStaticMarkup(
      <FilePreview isOpen={true} files={[textFile]} />,
    );

    const editButton = renderedButtons.find(
      (button) => button.children === "file_preview.text.edit",
    );
    editButton?.onClick?.();

    expect(html).toContain("text-preview:Notes.txt");
    expect(html).toContain("file_preview.text.edit");
    expect(setIsEditingText).toHaveBeenCalledWith(true);
  });

  it("selects the direct file URL for PDF previews", () => {
    const pdfFile = buildPreviewFile({
      id: "pdf-1",
      title: "Demo.pdf",
      filename: "Demo.pdf",
      mimetype: "application/pdf",
      category: MimeCategory.PDF,
      url_preview: "https://example.test/preview/Demo.pdf",
      url: "https://example.test/original/Demo.pdf",
    });

    expect(getPdfPreviewSrc(pdfFile)).toBe(
      "https://example.test/original/Demo.pdf",
    );
    expect(
      getPdfPreviewSrc({
        ...pdfFile,
        stream_url: "https://example.test/stream/Demo.pdf",
      }),
    ).toBe("https://example.test/stream/Demo.pdf");
  });

  it("normalizes loopback PDF URLs to the current browser host", () => {
    const globalWithWindow = globalThis as typeof globalThis & {
      window?: { location: { hostname: string; protocol: string } };
    };
    const originalWindow = globalWithWindow.window;

    Object.defineProperty(globalWithWindow, "window", {
      configurable: true,
      value: { location: { hostname: "127.0.0.1", protocol: "http:" } },
    });

    expect(
      getPdfPreviewSrc(
        buildPreviewFile({
          mimetype: "application/pdf",
          category: MimeCategory.PDF,
          url: "http://localhost:8083/media/demo.pdf",
        }),
      ),
    ).toBe("http://127.0.0.1:8083/media/demo.pdf");

    expect(
      getPdfPreviewSrc(
        buildPreviewFile({
          mimetype: "application/pdf",
          category: MimeCategory.PDF,
          url: "http://192.168.10.123:8083/media/demo.pdf",
        }),
      ),
    ).toBe("http://127.0.0.1:8083/media/demo.pdf");

    expect(
      getPdfPreviewSrc(
        buildPreviewFile({
          mimetype: "application/pdf",
          category: MimeCategory.PDF,
          url: "https://media.example.test/media/demo.pdf",
        }),
      ),
    ).toBe("https://media.example.test/media/demo.pdf");

    Object.defineProperty(globalWithWindow, "window", {
      configurable: true,
      value: originalWindow,
    });
  });

  it("keeps custom preview source overrides routed through the generic host", () => {
    useStateSpy = jest
      .spyOn(React, "useState")
      .mockImplementation(realUseState as never)
      .mockImplementationOnce((() => [0, jest.fn()]) as never);

    const wopiFile = buildPreviewFile({
      id: "wopi-1",
      title: "Doc",
      filename: "Doc.docx",
      mimetype: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      category: MimeCategory.OTHER,
      preview_kind: "wopi",
    });
    const renderWopiEditor = jest.fn(() => <div>custom-wopi-renderer</div>);
    const source = {
      renderWopiEditor,
    } satisfies PreviewSource;

    mockedUseResolvedPreviewFile.mockReturnValue({
      effectiveCurrentFile: wopiFile,
      isResolvingCurrentFile: false,
      resolvedPreviewQuery: {
        isError: false,
        error: null,
        refetch: jest.fn(),
      },
    } as never);

    const html = renderToStaticMarkup(
      <FilePreview isOpen={true} files={[wopiFile]} source={source} />,
    );

    expect(html).toContain("custom-wopi-renderer");
    expect(renderWopiEditor).toHaveBeenCalledWith(
      wopiFile,
      undefined,
      undefined,
    );
  });
});
