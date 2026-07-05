import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useRouter } from "next/router";

import { fetchAPI } from "@/features/api/fetchApi";

import MountShareLinkPage from "../[token]";

jest.mock("next/router", () => ({
  useRouter: jest.fn(),
}));

jest.mock("@/features/api/fetchApi", () => ({
  fetchAPI: jest.fn(),
}));

const mockedUseRouter = jest.mocked(useRouter);
const mockedFetchAPI = jest.mocked(fetchAPI);

describe("MountShareLinkPage", () => {
  beforeEach(() => {
    mockedUseRouter.mockReturnValue({
      pathname: "/share/mount/[token]",
      push: jest.fn(),
      query: {
        token: "mount-token",
      },
    } as never);
    mockedFetchAPI.mockReset();
  });

  it("starts the mount browse request with token and optional path", () => {
    const useEffectSpy = jest.spyOn(React, "useEffect");
    const useStateSpy = jest.spyOn(React, "useState");
    mockedUseRouter.mockReturnValue({
      pathname: "/share/mount/[token]",
      push: jest.fn(),
      query: {
        path: "/docs",
        token: "mount-token",
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
      .mockReturnValueOnce([null, jest.fn()] as never)
      .mockReturnValueOnce([null, jest.fn()] as never)
      .mockReturnValueOnce([false, jest.fn()] as never);

    renderToStaticMarkup(<MountShareLinkPage />);

    expect(mockedFetchAPI).toHaveBeenCalledWith(
      "mount-share-links/mount-token/browse/",
      { params: { path: "/docs" } },
      { redirectOn40x: false, timeoutMs: 15000 },
    );

    useEffectSpy.mockRestore();
    useStateSpy.mockRestore();
  });

  it("renders the gone error branch", () => {
    const useStateSpy = jest.spyOn(React, "useState");
    useStateSpy
      .mockReturnValueOnce([null, jest.fn()] as never)
      .mockReturnValueOnce(["gone", jest.fn()] as never)
      .mockReturnValueOnce([false, jest.fn()] as never);

    const html = renderToStaticMarkup(<MountShareLinkPage />);

    expect(html).toContain("Link unavailable");
    expect(html).toContain(
      "Link expired or target moved. Ask the sender to create a new link.",
    );

    useStateSpy.mockRestore();
  });

  it("renders folder navigation with back-to-root", () => {
    const useStateSpy = jest.spyOn(React, "useState");
    useStateSpy
      .mockReturnValueOnce([
        {
          children: {
            count: 1,
            next: null,
            previous: null,
            results: [
              {
                entry_type: "folder",
                name: "Nested folder",
                normalized_path: "/docs/nested",
              },
            ],
          },
          entry: {
            entry_type: "folder",
            name: "Docs",
            normalized_path: "/docs",
          },
          normalized_path: "/docs",
        },
        jest.fn(),
      ] as never)
      .mockReturnValueOnce([null, jest.fn()] as never)
      .mockReturnValueOnce([false, jest.fn()] as never);

    const html = renderToStaticMarkup(<MountShareLinkPage />);

    expect(html).toContain("Docs");
    expect(html).toContain("Back to root");
    expect(html).toContain("Nested folder");

    useStateSpy.mockRestore();
  });

  it("renders the shared file message when the current entry is a file", () => {
    const useStateSpy = jest.spyOn(React, "useState");
    useStateSpy
      .mockReturnValueOnce([
        {
          children: null,
          entry: {
            entry_type: "file",
            name: "Shared file",
            normalized_path: "/Shared file",
          },
          normalized_path: "/Shared file",
        },
        jest.fn(),
      ] as never)
      .mockReturnValueOnce([null, jest.fn()] as never)
      .mockReturnValueOnce([false, jest.fn()] as never);

    const html = renderToStaticMarkup(<MountShareLinkPage />);

    expect(html).toContain("Shared file");
    expect(html).toContain(
      "This file is shared, but download is not available yet.",
    );

    useStateSpy.mockRestore();
  });
});
