import { useTreeContext } from "@gouvfr-lasuite/ui-kit";

import { useTreeUtils } from "../useTreeUtils";

jest.mock("@gouvfr-lasuite/ui-kit", () => ({
  useTreeContext: jest.fn(),
  TreeViewNodeTypeEnum: {
    NODE: "node",
    FOLDER: "folder",
  },
}));

const mockedUseTreeContext = jest.mocked(useTreeContext);

const buildNode = (
  id: string,
  originalId: string,
  children: Array<unknown> = [],
) => ({
  value: {
    id,
    nodeType: "node",
    originalId,
  },
  children,
});

describe("useTreeUtils", () => {
  const deleteNodes = jest.fn();
  const updateNode = jest.fn();

  beforeEach(() => {
    deleteNodes.mockReset();
    updateNode.mockReset();
  });

  it("finds every tree occurrence of a given original id recursively", () => {
    mockedUseTreeContext.mockReturnValue({
      treeData: {
        nodes: [
          buildNode("tree-1", "original-a"),
          buildNode("tree-2", "other", [
            buildNode("tree-3", "original-a"),
            buildNode("tree-4", "original-b", [
              buildNode("tree-5", "original-a"),
            ]),
          ]),
        ],
        deleteNodes,
        updateNode,
      },
    } as never);

    const utils = useTreeUtils();

    expect(utils.findAllTreeIdsByOriginalId("original-a")).toEqual([
      "tree-1",
      "tree-3",
      "tree-5",
    ]);
    expect(utils.findAllTreeIdsByOriginalId("missing")).toEqual([]);
  });

  it("returns an empty list when the tree context has no nodes yet", () => {
    mockedUseTreeContext.mockReturnValue({
      treeData: {
        nodes: undefined,
        deleteNodes,
        updateNode,
      },
    } as never);

    const utils = useTreeUtils();

    expect(utils.findAllTreeIdsByOriginalId("original-a")).toEqual([]);
  });

  it("deletes every occurrence of an original id and reports the deleted count", () => {
    mockedUseTreeContext.mockReturnValue({
      treeData: {
        nodes: [
          buildNode("tree-1", "original-a"),
          buildNode("tree-2", "original-a"),
          buildNode("tree-3", "other"),
        ],
        deleteNodes,
        updateNode,
      },
    } as never);

    const utils = useTreeUtils();

    expect(utils.deleteAllByOriginalId("original-a")).toBe(2);
    expect(deleteNodes).toHaveBeenCalledWith(["tree-1", "tree-2"]);
  });

  it("updates every occurrence of an original id with the same partial update", () => {
    mockedUseTreeContext.mockReturnValue({
      treeData: {
        nodes: [
          buildNode("tree-1", "original-a"),
          buildNode("tree-2", "other", [buildNode("tree-3", "original-a")]),
        ],
        deleteNodes,
        updateNode,
      },
    } as never);

    const utils = useTreeUtils();

    utils.updateNodeByOriginalId("original-a", { title: "Renamed" });

    expect(updateNode).toHaveBeenNthCalledWith(1, "tree-1", {
      title: "Renamed",
    });
    expect(updateNode).toHaveBeenNthCalledWith(2, "tree-3", {
      title: "Renamed",
    });
  });
});
