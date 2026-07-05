import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useTranslation } from "react-i18next";
import { ModalSize, useModals } from "@gouvfr-lasuite/cunningham-react";

import { Item, ItemType, ItemUploadState } from "@/features/drivers/types";
import { useAuth } from "@/features/auth/Auth";
import { addToast } from "@/features/ui/components/toaster/Toaster";

import { downloadFile } from "../../utils";
import { useDownloadItem } from "../useDownloadItem";

jest.mock("react-i18next", () => ({
  useTranslation: jest.fn(),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  ModalSize: {
    MEDIUM: "medium",
  },
  useModals: jest.fn(),
}));

jest.mock("@/features/auth/Auth", () => ({
  useAuth: jest.fn(),
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

jest.mock("../../utils", () => ({
  downloadFile: jest.fn(),
}));

jest.mock("posthog-js", () => ({
  __esModule: true,
  default: {
    capture: jest.fn(),
  },
}));

const mockedUseTranslation = jest.mocked(useTranslation);
const mockedUseModals = jest.mocked(useModals);
const mockedUseAuth = jest.mocked(useAuth);
const mockedAddToast = jest.mocked(addToast);
const mockedDownloadFile = jest.mocked(downloadFile);
const mockedPosthog = jest.requireMock("posthog-js").default as {
  capture: jest.Mock;
};

const baseItem: Item = {
  abilities: {
    children_create: false,
  },
  creator: {
    id: "owner-1",
  },
  id: "item-1",
  mimetype: "application/pdf",
  size: 123,
  title: "Report.pdf",
  type: ItemType.FILE,
  upload_state: ItemUploadState.READY,
  url: "https://download.example.test/report.pdf",
} as never;

describe("useDownloadItem", () => {
  let handleDownloadItem:
    | ((item?: Item) => Promise<void>)
    | undefined;
  const confirmationModal = jest.fn();

  const Probe = () => {
    ({ handleDownloadItem } = useDownloadItem());
    return <div>probe</div>;
  };

  beforeEach(() => {
    confirmationModal.mockReset();
    mockedAddToast.mockReset();
    mockedDownloadFile.mockReset();
    mockedPosthog.capture.mockReset();
    mockedUseTranslation.mockReturnValue({
      t: (key: string) => `translated:${key}`,
    } as never);
    mockedUseModals.mockReturnValue({
      confirmationModal,
    } as never);
    mockedUseAuth.mockReturnValue({
      user: { id: "owner-1" },
    } as never);
    renderToStaticMarkup(<Probe />);
  });

  it("shows the expired upload error when there is no downloadable url or title", async () => {
    await handleDownloadItem?.({
      ...baseItem,
      title: "",
      upload_state: ItemUploadState.EXPIRED,
      url: "",
    });

    expect(
      renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as React.ReactElement),
    ).toContain("translated:file_download_modal.error.upload_expired");
    expect(mockedDownloadFile).not.toHaveBeenCalled();
  });

  it("shows the not-ready error for pending and analyzing uploads", async () => {
    await handleDownloadItem?.({
      ...baseItem,
      title: "",
      upload_state: ItemUploadState.PENDING,
      url: "",
    });

    expect(
      renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as React.ReactElement),
    ).toContain("translated:file_download_modal.error.not_ready");
  });

  it("asks the creator to confirm suspicious files before downloading", async () => {
    confirmationModal.mockResolvedValue("yes");

    await handleDownloadItem?.({
      ...baseItem,
      upload_state: ItemUploadState.SUSPICIOUS,
    });

    expect(confirmationModal).toHaveBeenCalledWith({
      children: "translated:file_download_modal.description",
      size: ModalSize.MEDIUM,
      title: "translated:file_download_modal.suspicious.title",
    });
    expect(mockedPosthog.capture).toHaveBeenCalledWith("file_download", {
      id: "item-1",
      mimetype: "application/pdf",
      size: 123,
    });
    expect(mockedDownloadFile).toHaveBeenCalledWith(
      "https://download.example.test/report.pdf",
      "Report.pdf",
    );
  });

  it("asks non-creators to confirm files that are too large to analyze", async () => {
    mockedUseAuth.mockReturnValue({
      user: { id: "viewer-2" },
    } as never);
    renderToStaticMarkup(<Probe />);
    confirmationModal.mockResolvedValue("no");

    await handleDownloadItem?.({
      ...baseItem,
      creator: {
        id: "owner-1",
        full_name: "Owner",
        short_name: "OW",
      },
      upload_state: ItemUploadState.FILE_TOO_LARGE_TO_ANALYZE,
    });

    expect(confirmationModal).toHaveBeenCalledWith({
      children: "translated:file_download_modal.description",
      size: ModalSize.MEDIUM,
      title: "translated:file_download_modal.file_too_large.title",
    });
    expect(mockedDownloadFile).not.toHaveBeenCalled();
  });

  it("downloads immediately and tracks analytics when no confirmation is needed", async () => {
    await handleDownloadItem?.(baseItem);

    expect(confirmationModal).not.toHaveBeenCalled();
    expect(mockedPosthog.capture).toHaveBeenCalledWith("file_download", {
      id: "item-1",
      mimetype: "application/pdf",
      size: 123,
    });
    expect(mockedDownloadFile).toHaveBeenCalledWith(
      "https://download.example.test/report.pdf",
      "Report.pdf",
    );
  });
});
