import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useRouter } from "next/router";

import { fetchAPI } from "@/features/api/fetchApi";
import { ItemType } from "@/features/drivers/types";

import ShareLinkPage from "../[token]";

jest.mock("next/router", () => ({
  useRouter: jest.fn(),
}));

jest.mock("@/features/api/fetchApi", () => ({
  fetchAPI: jest.fn(),
}));

const mockedUseRouter = jest.mocked(useRouter);
const mockedFetchAPI = jest.mocked(fetchAPI);

describe("ShareLinkPage", () => {
  beforeEach(() => {
    mockedUseRouter.mockReturnValue({
      pathname: "/share/[token]",
      push: jest.fn(),
      query: {
        token: "public-token",
      },
    } as never);
    mockedFetchAPI.mockReset();
  });

  it("starts the public browse request with token and optional item_id", () => {
    const setData = jest.fn();
    const setError = jest.fn();
    const setLoading = jest.fn();
    const useEffectSpy = jest.spyOn(React, "useEffect");
    const useStateSpy = jest.spyOn(React, "useState");

    mockedUseRouter.mockReturnValue({
      pathname: "/share/[token]",
      push: jest.fn(),
      query: {
        item_id: "folder-2",
        token: "public-token",
      },
    } as never);
    mockedFetchAPI.mockReturnValue(
      Promise.resolve({
        json: async () => ({}),
      } as never),
    );
    useEffectSpy.mockImplementation((effect) => {
      effect();
    });
    useStateSpy
      .mockReturnValueOnce([null, setData] as never)
      .mockReturnValueOnce([null, setError] as never)
      .mockReturnValueOnce([false, setLoading] as never);

    renderToStaticMarkup(<ShareLinkPage />);

    expect(mockedFetchAPI).toHaveBeenCalledWith(
      "share-links/public-token/browse/",
      { params: { item_id: "folder-2" } },
      { redirectOn40x: false, timeoutMs: 15000 },
    );

    useEffectSpy.mockRestore();
    useStateSpy.mockRestore();
  });

  it("renders the loading branch", () => {
    const useStateSpy = jest.spyOn(React, "useState");
    useStateSpy
      .mockReturnValueOnce([null, jest.fn()] as never)
      .mockReturnValueOnce([null, jest.fn()] as never)
      .mockReturnValueOnce([true, jest.fn()] as never);

    const html = renderToStaticMarkup(<ShareLinkPage />);

    expect(html).toContain("Opening link");
    expect(html).toContain("Please wait.");

    useStateSpy.mockRestore();
  });

  it("renders the timeout error branch", () => {
    const useStateSpy = jest.spyOn(React, "useState");
    useStateSpy
      .mockReturnValueOnce([null, jest.fn()] as never)
      .mockReturnValueOnce(["timeout", jest.fn()] as never)
      .mockReturnValueOnce([false, jest.fn()] as never);

    const html = renderToStaticMarkup(<ShareLinkPage />);

    expect(html).toContain("Link unavailable");
    expect(html).toContain("This is taking too long. Please retry.");

    useStateSpy.mockRestore();
  });

  it("renders folder navigation with back-to-root and file links", () => {
    const push = jest.fn();
    const useStateSpy = jest.spyOn(React, "useState");
    mockedUseRouter.mockReturnValue({
      pathname: "/share/[token]",
      push,
      query: {
        item_id: "folder-2",
        token: "public-token",
      },
    } as never);
    useStateSpy
      .mockReturnValueOnce([
        {
          children: {
            count: 2,
            next: null,
            previous: null,
            results: [
              {
                id: "folder-child",
                title: "Nested folder",
                type: ItemType.FOLDER,
                url: null,
              },
              {
                id: "file-child",
                title: "Public file",
                type: ItemType.FILE,
                url: "https://download.example.test/file",
              },
            ],
          },
          item: {
            id: "folder-2",
            title: "Folder title",
            type: ItemType.FOLDER,
            url: null,
          },
          root_item_id: "root-item",
        },
        jest.fn(),
      ] as never)
      .mockReturnValueOnce([null, jest.fn()] as never)
      .mockReturnValueOnce([false, jest.fn()] as never);

    const html = renderToStaticMarkup(<ShareLinkPage />);

    expect(html).toContain("Folder title");
    expect(html).toContain("Back to root");
    expect(html).toContain("Nested folder");
    expect(html).toContain("https://download.example.test/file");

    useStateSpy.mockRestore();
  });

  it("renders file download when the current entry is a file", () => {
    const useStateSpy = jest.spyOn(React, "useState");
    useStateSpy
      .mockReturnValueOnce([
        {
          children: null,
          item: {
            id: "file-1",
            title: "Standalone file",
            type: ItemType.FILE,
            url: "https://download.example.test/file-1",
          },
          root_item_id: "file-1",
        },
        jest.fn(),
      ] as never)
      .mockReturnValueOnce([null, jest.fn()] as never)
      .mockReturnValueOnce([false, jest.fn()] as never);

    const html = renderToStaticMarkup(<ShareLinkPage />);

    expect(html).toContain("Standalone file");
    expect(html).toContain("Download");
    expect(html).toContain("https://download.example.test/file-1");

    useStateSpy.mockRestore();
  });
});
