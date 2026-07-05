import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ItemType } from "@/features/drivers/types";
import { addToast } from "@/features/ui/components/toaster/Toaster";
import {
  canUnzipItem,
  canZipSelection,
  openArchiveItemModal,
  showArchiveZipLowRightsToast,
} from "../archiveActionEntrypoints";

jest.mock("@/features/ui/components/toaster/Toaster", () => ({
  addToast: jest.fn(),
  ToasterItem: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

const mockedAddToast = jest.mocked(addToast);

describe("archiveActionEntrypoints", () => {
  beforeEach(() => {
    mockedAddToast.mockReset();
  });

  it("centralizes zip and unzip eligibility without changing their distinct semantics", () => {
    expect(
      canZipSelection([
        { abilities: { retrieve: true } } as never,
        { abilities: { retrieve: true } } as never,
      ]),
    ).toBe(true);
    expect(
      canZipSelection([
        { abilities: { retrieve: true } } as never,
        { abilities: { retrieve: false } } as never,
      ]),
    ).toBe(false);

    expect(
      canUnzipItem({
        abilities: { retrieve: true },
        filename: "archive.zip",
        title: "archive.zip",
        type: ItemType.FILE,
      } as never),
    ).toBe(true);
    expect(
      canUnzipItem(
        {
          abilities: { retrieve: true },
          filename: "archive.zip",
          title: "archive.zip",
          type: ItemType.FILE,
        } as never,
        { minimal: true },
      ),
    ).toBe(false);
    expect(
      canUnzipItem({
        abilities: { retrieve: false },
        filename: "archive.zip",
        title: "archive.zip",
        type: ItemType.FILE,
      } as never),
    ).toBe(false);
  });

  it("centralizes the zip low-rights toast", () => {
    showArchiveZipLowRightsToast((key) => key);

    expect(mockedAddToast).toHaveBeenCalledTimes(1);
    expect(renderToStaticMarkup(mockedAddToast.mock.calls[0][0] as never)).toContain(
      "explorer.actions.archive.zip.low_rights_toast",
    );
  });

  it("centralizes archive item modal opening for item-scoped actions", () => {
    const setCurrentItem = jest.fn();
    const openModal = jest.fn();
    const item = { id: "archive-1", title: "Archive.zip" };

    openArchiveItemModal({
      item,
      openModal,
      setCurrentItem,
    });

    expect(setCurrentItem).toHaveBeenCalledWith(item);
    expect(openModal).toHaveBeenCalled();
  });
});
