import { flattenBrowsePages } from "../browseTemplateUtils";
import { Item, ItemType } from "@/features/drivers/types";

const makeItem = (id: string): Item =>
  ({
  id,
  title: id,
  filename: `${id}.txt`,
  creator: {
    id: "tester",
    full_name: "Tester",
    short_name: "TS",
  },
  type: ItemType.FILE,
  ancestors_link_reach: null,
  ancestors_link_role: null,
  computed_link_reach: null,
  computed_link_role: null,
  upload_state: "ready",
  updated_at: new Date("2024-01-01T00:00:00Z"),
  description: "",
  created_at: new Date("2024-01-01T00:00:00Z"),
  path: `/${id}.txt`,
  link_reach: "restricted",
  link_role: "reader",
  abilities: {
    accesses_manage: false,
    accesses_view: false,
    children_create: false,
    children_list: false,
    destroy: false,
    favorite: false,
    invite_owner: false,
    link_configuration: false,
    media_auth: false,
    move: false,
    link_select_options: {
      restricted: null,
      authenticated: null,
      public: null,
    },
    partial_update: false,
    restore: false,
    retrieve: true,
    tree: false,
    update: false,
    upload_ended: false,
  },
}) as Item;

describe("BrowseExplorerTemplate", () => {
  it("flattens paginated browse data through the provided adapter mapper", () => {
    expect(
      flattenBrowsePages(
        [
          { entries: [makeItem("a"), makeItem("b")] },
          { entries: [makeItem("c")] },
        ],
        (page) => page.entries,
      ),
    ).toEqual([makeItem("a"), makeItem("b"), makeItem("c")]);
  });

  it("returns an empty array when no pages are loaded yet", () => {
    expect(
      flattenBrowsePages(undefined, () => {
        throw new Error("mapper should not run without pages");
      }),
    ).toEqual([]);
  });
});
