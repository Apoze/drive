import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useDropdownMenu } from "@gouvfr-lasuite/ui-kit";
import { ImportDropdown } from "../ImportDropdown";

const capturedDropdownOptions: unknown[] = [];

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  DropdownMenu: ({ options, children }: { options: unknown; children?: React.ReactNode }) => {
    capturedDropdownOptions.push(options);
    return <div>{children}</div>;
  },
  useDropdownMenu: jest.fn(),
}));

const mockedUseDropdownMenu = jest.mocked(useDropdownMenu);

describe("ImportDropdown", () => {
  beforeEach(() => {
    capturedDropdownOptions.length = 0;
    Object.defineProperty(globalThis, "document", {
      configurable: true,
      value: {
        getElementById: jest.fn((id: string) => ({
          click: jest.fn(() => id),
        })),
      },
    });
  });

  it("routes file and folder import actions through the shared hidden inputs", () => {
    const importMenu = {
      isOpen: false,
      setIsOpen: jest.fn(),
    };
    mockedUseDropdownMenu.mockReturnValue(importMenu as never);

    renderToStaticMarkup(
      <ImportDropdown
        importMenu={importMenu as never}
        trigger={<button>trigger</button>}
      />,
    );

    const options = capturedDropdownOptions[0] as Array<{
      label: string;
      callback?: () => void;
    }>;

    const importFiles = options.find(
      (option) => option.label === "explorer.tree.import.files",
    );
    const importFolders = options.find(
      (option) => option.label === "explorer.tree.import.folders",
    );

    importFiles?.callback?.();
    importFolders?.callback?.();

    expect(document.getElementById).toHaveBeenCalledWith("import-files");
    expect(document.getElementById).toHaveBeenCalledWith("import-folders");
  });
});
