import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useVirtualizer } from "@tanstack/react-virtual";
import { getIconByMimeType } from "@/features/explorer/components/icons/ItemIcon";
import { useArchiveViewerExtractController } from "../archiveViewerExtractController";
import { useArchiveViewerListController } from "../archiveViewerListController";
import { useArchiveViewerLoadController } from "../archiveViewerLoadController";
import { useArchiveViewerPreviewController } from "../archiveViewerPreviewController";
import { ArchiveViewer } from "../ArchiveViewer";

const buttonProps: Array<{
  children?: React.ReactNode;
  disabled?: boolean;
  onClick?: () => void;
}> = [];

const archiveExtractionModalProps: Array<{
  initialFolderId?: string;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (folderId: string | undefined) => Promise<void>;
}> = [];

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Button: (props: {
    children?: React.ReactNode;
    disabled?: boolean;
    onClick?: () => void;
  }) => {
    buttonProps.push(props);
    return <button>{props.children}</button>;
  },
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  Icon: ({ name }: { name: string }) => <span>{name}</span>,
}));

jest.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: jest.fn(),
}));

jest.mock("pretty-bytes", () => ({
  __esModule: true,
  default: (value: number) => `${value} B`,
}));

jest.mock("react-toastify", () => ({
  toast: {
    error: jest.fn(),
    success: jest.fn(),
  },
}));

jest.mock("../ArchiveExtractionModal", () => ({
  ArchiveExtractionModal: (props: {
    initialFolderId?: string;
    isOpen: boolean;
    onClose: () => void;
    onConfirm: (folderId: string | undefined) => Promise<void>;
  }) => {
    archiveExtractionModalProps.push(props);
    return props.isOpen ? <div>archive-extraction-modal-open</div> : null;
  },
}));

jest.mock("../archiveZipWorkerFactory", () => ({
  createArchiveZipWorker: jest.fn(),
}));

jest.mock("../archiveViewerListController", () => ({
  getArchiveEntryDisplayParts: (path: string) => {
    const parts = path.split("/");
    const name = parts.pop() || path;
    return {
      dir: parts.join("/"),
      name,
    };
  },
  useArchiveViewerListController: jest.fn(),
}));

jest.mock("../archiveViewerPreviewController", () => ({
  useArchiveViewerPreviewController: jest.fn(),
}));

jest.mock("@/features/explorer/components/icons/ItemIcon", () => ({
  getIconByMimeType: jest.fn(),
}));

jest.mock("../archiveViewerLoadController", () => ({
  useArchiveViewerLoadController: jest.fn(),
}));

jest.mock("../archiveViewerExtractController", () => ({
  useArchiveViewerExtractController: jest.fn(),
}));

const mockedUseVirtualizer = jest.mocked(useVirtualizer);
const mockedGetIconByMimeType = jest.mocked(getIconByMimeType);
const mockedUseArchiveViewerExtractController = jest.mocked(
  useArchiveViewerExtractController,
);
const mockedUseArchiveViewerListController = jest.mocked(
  useArchiveViewerListController,
);
const mockedUseArchiveViewerLoadController = jest.mocked(
  useArchiveViewerLoadController,
);
const mockedUseArchiveViewerPreviewController = jest.mocked(
  useArchiveViewerPreviewController,
);

const archiveItem = {
  id: "archive-1",
  mimetype: "application/zip",
  size: 128,
  title: "demo.zip",
  url: "https://example.test/demo.zip",
};

describe("ArchiveViewer", () => {
  beforeEach(() => {
    buttonProps.length = 0;
    archiveExtractionModalProps.length = 0;
    jest.clearAllMocks();
    jest.restoreAllMocks();

    mockedUseVirtualizer.mockImplementation(
      ({ count }: { count: number }) =>
        ({
          getTotalSize: () => count * 52,
          getVirtualItems: () =>
            Array.from({ length: count }, (_, index) => ({
              index,
              key: index,
              size: 52,
              start: index * 52,
            })),
        }) as never,
    );
    mockedGetIconByMimeType.mockReturnValue({
      src: "/icon.svg",
    } as never);
    mockedUseArchiveViewerLoadController.mockReturnValue({
      backend: "zip",
      entries: [],
      error: null,
      loading: false,
    } as never);
    mockedUseArchiveViewerExtractController.mockReturnValue({
      defaultDestinationFolderId: "parent-folder",
      extractionStatus: {
        data: null,
        isFetching: false,
      },
      isExtractModalOpen: false,
      jobId: null,
      onCloseExtractModal: jest.fn(),
      onConfirmExtract: jest.fn(),
      onOpenExtractModal: jest.fn(),
    } as never);
    mockedUseArchiveViewerListController.mockReturnValue({
      filteredEntries: [],
      query: "",
      selectedEntry: null,
      selectedPath: null,
      setQuery: jest.fn(),
      setSelectedPath: jest.fn(),
      sortDir: "asc",
      sortKey: "name",
      toggleSort: jest.fn(),
    } as never);
    mockedUseArchiveViewerPreviewController.mockReturnValue({
      onDownloadSelected: jest.fn(),
      previewError: null,
      previewImageUrl: "",
      previewKind: "empty",
      previewLoading: false,
      previewText: "",
    } as never);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("renders directly and forwards the derived default extraction folder", () => {
    const html = renderToStaticMarkup(
      <ArchiveViewer archiveDetailsItemId="details-1" archiveItem={archiveItem} />,
    );

    expect(html).toContain("archive_viewer.contents_title");
    expect(html).toContain("archive_viewer.actions.extract_all");
    expect(html).toContain("archive_viewer.actions.extract_selected");
    expect(archiveExtractionModalProps).toEqual([
      expect.objectContaining({
        initialFolderId: "parent-folder",
        isOpen: false,
      }),
    ]);
  });

  it("renders a representative selected-file preview and inline extract status", () => {
    mockedUseArchiveViewerLoadController.mockReturnValue({
      backend: "zip",
      entries: [
        {
          path: "docs/readme.txt",
          isDirectory: false,
          uncompressedSize: 12,
        },
      ],
      error: null,
      loading: false,
    } as never);
    mockedUseArchiveViewerExtractController.mockReturnValue({
      defaultDestinationFolderId: "parent-folder",
      extractionStatus: {
        data: {
          progress: {
            files_done: 1,
            total: 1,
          },
          state: "running",
        },
        isFetching: false,
      },
      isExtractModalOpen: true,
      jobId: "job-1",
      onCloseExtractModal: jest.fn(),
      onConfirmExtract: jest.fn(),
      onOpenExtractModal: jest.fn(),
    } as never);

    mockedUseArchiveViewerListController.mockReturnValue({
      filteredEntries: [
        {
          path: "docs/readme.txt",
          isDirectory: false,
          uncompressedSize: 12,
        },
      ],
      query: "",
      selectedEntry: {
        path: "docs/readme.txt",
        isDirectory: false,
        uncompressedSize: 12,
      },
      selectedPath: "docs/readme.txt",
      setQuery: jest.fn(),
      setSelectedPath: jest.fn(),
      sortDir: "asc",
      sortKey: "name",
      toggleSort: jest.fn(),
    } as never);
    mockedUseArchiveViewerPreviewController.mockReturnValue({
      onDownloadSelected: jest.fn(),
      previewError: null,
      previewImageUrl: "",
      previewKind: "text",
      previewLoading: false,
      previewText: "hello archive",
    } as never);

    const html = renderToStaticMarkup(
      <ArchiveViewer archiveDetailsItemId="details-1" archiveItem={archiveItem} />,
    );

    expect(html).toContain("archive_viewer.extract.status");
    expect(html).toContain("readme.txt");
    expect(html).toContain("docs");
    expect(html).toContain("hello archive");
    expect(html).toContain("archive-extraction-modal-open");
    expect(html).toContain("archive_viewer.actions.download_file");
    expect(mockedUseArchiveViewerExtractController).toHaveBeenCalledWith(
      expect.objectContaining({
        archiveDetailsItemId: "details-1",
        archiveItemId: "archive-1",
        selectedPath: "docs/readme.txt",
      }),
    );
  });
});
