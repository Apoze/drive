import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import FilePage from "../[id]";
import { useItem } from "@/features/explorer/hooks/useQueries";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("next/router", () => ({
  useRouter: () => ({
    query: {
      id: "item-1",
    },
  }),
}));

jest.mock("@/features/explorer/hooks/useQueries", () => ({
  useItem: jest.fn(),
}));

jest.mock("@/features/ui/components/generic-disclaimer/GenericDisclaimer", () => ({
  GenericDisclaimer: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="generic-disclaimer">{children}</div>
  ),
}));

jest.mock("@/features/ui/components/spinner/SpinnerPage", () => ({
  SpinnerPage: () => <div data-testid="spinner-page" />,
}));

jest.mock("@/features/ui/preview/custom-files-preview/CustomFilesPreview", () => ({
  CustomFilesPreview: ({
    currentItem,
    items,
  }: {
    currentItem?: { title?: string };
    items: Array<{ title?: string }>;
  }) => (
    <div data-testid="standalone-custom-files-preview">
      {currentItem?.title}:{items.map((item) => item.title).join(",")}
    </div>
  ),
}));

const mockedUseItem = jest.mocked(useItem);

describe("items/files/[id] page", () => {
  beforeEach(() => {
    mockedUseItem.mockReset();
  });

  it("keeps the standalone items preview mounted directly on CustomFilesPreview", () => {
    mockedUseItem.mockReturnValue({
      data: {
        id: "item-1",
        title: "Standalone file",
      },
      isLoading: false,
      error: undefined,
    } as never);

    const html = renderToStaticMarkup(<FilePage />);

    expect(html).toContain("data-testid=\"standalone-custom-files-preview\"");
    expect(html).toContain("Standalone file:Standalone file");
  });
});
