import { ItemType } from "@/features/drivers/types";
import {
  buildItemUploadFilesMeta,
  buildItemUploadPlan,
  pathNicefy,
} from "../itemUploadPlan";
import { createEmptyFolderMarker } from "@/features/explorer/utils/dropTraversal";

const currentItem = {
  id: "folder-1",
  title: "Current folder",
  type: ItemType.FOLDER,
};

const buildFile = (name: string, path?: string) => ({
  name,
  path: path ?? name,
  size: 12,
  type: "text/plain",
});

describe("itemUploadPlan", () => {
  it("builds a nested folder plan from dropped file paths", () => {
    const upload = buildItemUploadPlan({
      currentItem: currentItem as never,
      files: [
        buildFile("report.txt", "./docs/report.txt"),
        buildFile("notes.txt", "/docs/nested/notes.txt"),
        buildFile("root.txt"),
      ] as never,
    });

    expect(upload.folder.item).toBe(currentItem);
    expect(upload.folder.files.map((file) => file.name)).toEqual(["root.txt"]);
    expect(upload.folder.children.map((folder) => folder.item.title)).toEqual(["docs"]);
    expect(upload.folder.children[0].files.map((file) => file.name)).toEqual([
      "report.txt",
    ]);
    expect(
      upload.folder.children[0].children[0].files.map((file) => file.name),
    ).toEqual(["notes.txt"]);
  });

  it("builds initial files meta with normalized relative paths", () => {
    const filesMeta = buildItemUploadFilesMeta([
      buildFile("report.txt", "./docs/report.txt"),
      buildFile("notes.txt", "/notes.txt"),
    ] as never);

    expect(Object.keys(filesMeta)).toEqual(["docs/report.txt", "notes.txt"]);
    expect(filesMeta["docs/report.txt"]).toMatchObject({
      progress: 0,
      status: "in_progress",
    });
    expect(pathNicefy("./docs/report.txt")).toBe("docs/report.txt");
    expect(pathNicefy("/notes.txt")).toBe("notes.txt");
  });

  it("uses empty-folder markers to create folder nodes without uploading marker files", () => {
    const marker = createEmptyFolderMarker("/docs/empty");
    const upload = buildItemUploadPlan({
      currentItem: currentItem as never,
      files: [marker] as never,
    });

    expect(upload.files).toEqual([]);
    expect(upload.folder.children.map((folder) => folder.item.title)).toEqual([
      "docs",
    ]);
    expect(upload.folder.children[0].children[0].item.title).toBe("empty");
    expect(upload.folder.children[0].children[0].files).toEqual([]);
  });
});
