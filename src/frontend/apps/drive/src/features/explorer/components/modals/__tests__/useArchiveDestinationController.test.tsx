import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { useItem } from "@/features/explorer/hooks/useQueries";
import { useArchiveDestinationController } from "../useArchiveDestinationController";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  useModal: jest.fn(),
}));

jest.mock("@/features/explorer/hooks/useQueries", () => ({
  useItem: jest.fn(),
}));

const mockedUseModal = jest.mocked(useModal);
const mockedUseItem = jest.mocked(useItem);

describe("useArchiveDestinationController", () => {
  it("centralizes archive destination label and pick-folder wiring", () => {
    let controller:
      | ReturnType<typeof useArchiveDestinationController>
      | undefined;

    mockedUseModal.mockReturnValue({
      close: jest.fn(),
      isOpen: true,
      open: jest.fn(),
    } as never);
    mockedUseItem.mockReturnValue({
      data: {
        title: "Destination folder",
      },
    } as never);

    const Harness = () => {
      controller = useArchiveDestinationController({
        initialDestinationFolderId: "folder-1",
        isOpen: true,
      });
      return null;
    };

    renderToStaticMarkup(<Harness />);

    expect(controller?.effectiveDestinationId).toBe("folder-1");
    expect(controller?.destinationLabel).toBe("Destination folder");
    expect(controller?.pickFolderModalProps).toMatchObject({
      initialFolderId: "folder-1",
      isOpen: true,
    });
  });
});
