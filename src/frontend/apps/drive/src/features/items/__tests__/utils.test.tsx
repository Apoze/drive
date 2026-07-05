import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useRouter } from "next/router";

import { ItemType } from "@/features/drivers/types";

import {
  canCreateChildren,
  downloadFile,
  useCanCreateChildren,
} from "../utils";

jest.mock("next/router", () => ({
  useRouter: jest.fn(),
}));

const mockedUseRouter = jest.mocked(useRouter);

describe("items/utils", () => {
  const originalDocument = global.document;

  afterEach(() => {
    if (originalDocument === undefined) {
      Object.defineProperty(global, "document", {
        configurable: true,
        value: undefined,
      });
    } else {
      Object.defineProperty(global, "document", {
        configurable: true,
        value: originalDocument,
      });
    }
  });

  it("downloads files through the hidden anchor pattern", async () => {
    const click = jest.fn();
    const appendChild = jest.fn();
    const removeChild = jest.fn();
    const anchor = {
      click,
      download: "",
      href: "",
      style: {},
    };

    Object.defineProperty(global, "document", {
      configurable: true,
      value: {
        body: {
          appendChild,
          removeChild,
        },
        createElement: jest.fn(() => anchor),
      },
    });

    await downloadFile("https://download.example.test/file.pdf", "file.pdf");

    expect(appendChild).toHaveBeenCalledWith(anchor);
    expect(anchor.href).toBe("https://download.example.test/file.pdf");
    expect(anchor.download).toBe("file.pdf");
    expect(click).toHaveBeenCalledTimes(1);
    expect(removeChild).toHaveBeenCalledWith(anchor);
  });

  it("allows child creation when the item ability is present or the route is my-files", () => {
    expect(
      canCreateChildren(
        {
          abilities: { children_create: true },
          type: ItemType.FOLDER,
        } as never,
        "/explorer/items/files",
      ),
    ).toBe(true);

    expect(
      canCreateChildren(
        {
          abilities: { children_create: false },
          type: ItemType.FOLDER,
        } as never,
        "/explorer/items/my-files",
      ),
    ).toBe(true);

    expect(
      canCreateChildren(
        {
          abilities: { children_create: false },
          type: ItemType.FOLDER,
        } as never,
        "/explorer/items/files",
      ),
    ).toBe(false);
  });

  it("derives the create-children ability from the current router pathname", () => {
    let canCreate: boolean | undefined;
    mockedUseRouter.mockReturnValue({
      pathname: "/explorer/items/my-files",
    } as never);

    const Probe = () => {
      canCreate = useCanCreateChildren({
        abilities: { children_create: false },
        type: ItemType.FOLDER,
      } as never);
      return <div>probe</div>;
    };

    renderToStaticMarkup(<Probe />);

    expect(canCreate).toBe(true);
  });
});
