import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useTranslation } from "react-i18next";

import { useItemActivity } from "@/features/explorer/hooks/useQueries";
import { ItemActivitySection } from "../ItemActivitySection";

jest.mock("react-i18next", () => ({
  useTranslation: jest.fn(),
}));

jest.mock("@/features/explorer/hooks/useQueries", () => ({
  useItemActivity: jest.fn(),
}));

const mockedUseTranslation = jest.mocked(useTranslation);
const mockedUseItemActivity = jest.mocked(useItemActivity);
const translate = jest.fn((key: string) => key);

const queryResult = (overrides = {}) => ({
  data: undefined,
  fetchNextPage: jest.fn(),
  hasNextPage: false,
  isError: false,
  isFetchingNextPage: false,
  isLoading: false,
  refetch: jest.fn(),
  ...overrides,
});

describe("ItemActivitySection", () => {
  beforeEach(() => {
    translate.mockClear();
    mockedUseTranslation.mockReturnValue({
      t: translate,
      i18n: { language: "en" },
    } as never);
    mockedUseItemActivity.mockReturnValue(queryResult() as never);
  });

  it("keeps the activity query disabled while the section is closed", () => {
    const html = renderToStaticMarkup(<ItemActivitySection itemId="item-1" />);

    expect(mockedUseItemActivity).toHaveBeenCalledWith("item-1", false);
    expect(html).toContain('aria-expanded="false"');
    expect(html).not.toContain("explorer.rightPanel.activity.empty");
  });

  it("renders localized activity, an exact accessible date, and load more", () => {
    const useStateSpy = jest.spyOn(React, "useState");
    useStateSpy.mockReturnValue([true, jest.fn()] as never);
    mockedUseItemActivity.mockReturnValue(
      queryResult({
        data: {
          pages: [
            {
              results: [
                {
                  id: "activity-1",
                  action: "renamed",
                  actor: "user-1",
                  actor_name: "Jane Doe",
                  payload: { old_name: "Old", new_name: "New" },
                  created_at: "2026-08-02T12:00:00Z",
                },
              ],
            },
          ],
        },
        hasNextPage: true,
      }) as never,
    );

    const html = renderToStaticMarkup(<ItemActivitySection itemId="item-1" />);

    expect(mockedUseItemActivity).toHaveBeenCalledWith("item-1", true);
    expect(translate).toHaveBeenCalledWith(
      "explorer.rightPanel.activity.actions.renamed",
      expect.objectContaining({
        actor: "Jane Doe",
        old_name: "Old",
        new_name: "New",
      }),
    );
    expect(html).toContain('dateTime="2026-08-02T12:00:00Z"');
    expect(html).toContain("aria-label=");
    expect(html).toContain("explorer.rightPanel.activity.load_more");

    useStateSpy.mockRestore();
  });

  it("renders empty and error states", () => {
    const useStateSpy = jest.spyOn(React, "useState");
    useStateSpy.mockReturnValue([true, jest.fn()] as never);

    const emptyHtml = renderToStaticMarkup(
      <ItemActivitySection itemId="item-1" />,
    );
    expect(emptyHtml).toContain("explorer.rightPanel.activity.empty");

    mockedUseItemActivity.mockReturnValue(
      queryResult({ isError: true }) as never,
    );
    const errorHtml = renderToStaticMarkup(
      <ItemActivitySection itemId="item-1" />,
    );
    expect(errorHtml).toContain("explorer.rightPanel.activity.error");
    expect(errorHtml).toContain("explorer.rightPanel.activity.retry");
    expect(errorHtml).not.toContain("explorer.rightPanel.activity.empty");

    useStateSpy.mockRestore();
  });
});
