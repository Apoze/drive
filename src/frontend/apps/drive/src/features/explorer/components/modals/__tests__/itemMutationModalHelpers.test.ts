import { ItemType, type Item } from "@/features/drivers/types";
import {
  buildCreateFileMutationPayload,
  buildNextRenamedRightPanelItem,
  canSubmitCreateFile,
  CREATE_FILE_EXTENSIONS_BY_KIND,
  filterCreateFileExtensionOptions,
  getCreateFileInitialState,
  getRenameInputTitle,
  getRenameMutationTitle,
  shouldRedirectToMyFiles,
  splitCreateFileExtensionOptions,
} from "../itemMutationModalHelpers";

const buildItem = (overrides: Partial<Item> = {}): Item => ({
  id: "item-1",
  title: "Report.txt",
  filename: "Report.txt",
  creator: {
    id: "user-1",
    full_name: "Jane Doe",
    short_name: "JD",
  },
  type: ItemType.FILE,
  ancestors_link_reach: null,
  ancestors_link_role: null,
  computed_link_reach: null,
  computed_link_role: null,
  upload_state: "ready",
  updated_at: new Date("2026-03-22T00:00:00Z"),
  description: "",
  created_at: new Date("2026-03-22T00:00:00Z"),
  path: "/Report.txt",
  mimetype: "text/plain",
  abilities: {
    accesses_manage: false,
    accesses_view: true,
    children_create: false,
    children_list: false,
    destroy: true,
    favorite: false,
    invite_owner: false,
    link_configuration: false,
    media_auth: false,
    move: true,
    link_select_options: {
      restricted: null,
      authenticated: null,
      public: null,
    },
    partial_update: true,
    restore: false,
    retrieve: true,
    tree: false,
    update: true,
    upload_ended: false,
  },
  ...overrides,
});

describe("itemMutationModalHelpers", () => {
  it("keeps create-file initial state deterministic for advanced and quick-create modes", () => {
    expect(getCreateFileInitialState()).toEqual({
      kind: "text",
      extension: "odt",
      filenameStem: "",
      extensionSearch: "",
    });

    expect(
      getCreateFileInitialState({
        kind: "slide",
        extension: "odp",
      }),
    ).toEqual({
      kind: "slide",
      extension: "odp",
      filenameStem: "",
      extensionSearch: "",
    });
  });

  it("filters and splits create-file extensions with the same matching rules as the modal", () => {
    const filtered = filterCreateFileExtensionOptions({
      options: CREATE_FILE_EXTENSIONS_BY_KIND.text,
      extensionSearch: "word",
      getLabel: (option) =>
        ({
          odt: "OpenDocument Text",
          docx: "Microsoft Word Document",
          doc: "Microsoft Word 97-2003",
          rtf: "Rich Text Format",
          txt: "Plain text",
          md: "Markdown",
          sh: "Shell script",
          ps1: "PowerShell script",
        })[option.labelKey] ?? option.labelKey,
    });
    const { recommended, others } = splitCreateFileExtensionOptions(filtered);

    expect(recommended).toEqual([]);
    expect(others.map((option) => option.ext)).toEqual(["docx", "doc"]);
  });

  it("builds the create-file payload from the current scope and submit state", () => {
    expect(
      canSubmitCreateFile({
        filenameStem: "  Quarterly plan  ",
        isPending: false,
      }),
    ).toBe(true);
    expect(
      buildCreateFileMutationPayload({
        parentId: "folder-1",
        canCreateChildren: false,
        filenameStem: "Quarterly plan",
        extension: "odt",
        kind: "text",
      }),
    ).toEqual({
      parentId: undefined,
      filenameStem: "Quarterly plan",
      extension: "odt",
      kind: "text",
    });
    expect(shouldRedirectToMyFiles(undefined)).toBe(true);
    expect(shouldRedirectToMyFiles("folder-1")).toBe(false);
  });

  it("centralizes rename input and right-panel sync rules", () => {
    const currentRightPanelItem = buildItem({
      id: "item-1",
      title: "Old title.txt",
      filename: "Old title.txt",
      path: "/Old title.txt",
    });

    expect(getRenameInputTitle(currentRightPanelItem)).toBe("Old title");
    expect(
      getRenameInputTitle(
        buildItem({
          type: ItemType.FOLDER,
          title: "Workspace",
          filename: "Workspace",
        }),
      ),
    ).toBe("Workspace");

    expect(
      getRenameMutationTitle({
        item: currentRightPanelItem,
        title: "Quarterly plan",
      }),
    ).toBe("Quarterly plan.txt");

    expect(
      buildNextRenamedRightPanelItem({
        currentItem: currentRightPanelItem,
        fallbackItem: buildItem({
          id: "item-1",
          title: "Fallback.txt",
        }),
        updatedItem: {
          id: "item-1",
          path: "/Quarterly plan.txt",
        },
        title: "Quarterly plan.txt",
      }),
    ).toMatchObject({
      id: "item-1",
      title: "Quarterly plan.txt",
      path: "/Quarterly plan.txt",
      filename: "Old title.txt",
    });
  });
});
