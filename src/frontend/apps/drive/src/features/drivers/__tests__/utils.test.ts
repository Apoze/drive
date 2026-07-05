import { ItemType } from "../types";
import { itemIsWorkspace } from "../utils";

describe("drivers/utils", () => {
  it("detects top-level non-main folders as workspaces", () => {
    expect(
      itemIsWorkspace({
        main_workspace: false,
        path: "workspace",
        type: ItemType.FOLDER,
      } as never),
    ).toBe(true);
  });

  it("rejects main workspaces and nested folders", () => {
    expect(
      itemIsWorkspace({
        main_workspace: true,
        path: "workspace",
        type: ItemType.FOLDER,
      } as never),
    ).toBe(false);

    expect(
      itemIsWorkspace({
        main_workspace: false,
        path: "workspace.child",
        type: ItemType.FOLDER,
      } as never),
    ).toBe(false);
  });

  it("rejects non-folder items", () => {
    expect(
      itemIsWorkspace({
        main_workspace: false,
        path: "workspace",
        type: ItemType.FILE,
      } as never),
    ).toBe(false);
  });
});
