import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { AddFolderButton } from "../AddFolderButton";

describe("AddFolderButton", () => {
  it("renders the same icon without invalid JSX DOM property warnings", () => {
    const consoleErrorSpy = jest
      .spyOn(console, "error")
      .mockImplementation(() => undefined);

    const html = renderToStaticMarkup(<AddFolderButton />);

    expect(html).toContain("add-folder-icon");
    expect(html).toContain("<svg");
    expect(
      consoleErrorSpy.mock.calls.some((call) =>
        call.join(" ").includes("Invalid DOM property"),
      ),
    ).toBe(false);

    consoleErrorSpy.mockRestore();
  });
});
