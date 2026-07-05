import { MountVirtualEntry } from "@/features/drivers/types";
import { MountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";
import {
  MountMovePreflightResult,
  isSameOrDescendantMountPath,
  resolveMountMovePreflight,
} from "@/features/mounts/utils/mountBulkActions";

export const resolveMountMoveModalState = ({
  items,
  currentPath,
  destinationEntries,
  isLoading,
  isError,
}: {
  items: MountExplorerItem[];
  currentPath: string;
  destinationEntries?: MountVirtualEntry[];
  isLoading: boolean;
  isError: boolean;
}) => {
  const childFolders = (destinationEntries ?? []).filter((entry) => {
    if (entry.entry_type !== "folder") {
      return false;
    }
    if (
      items.some(
        (item) =>
          item.mountMeta.entryType === "folder" &&
          isSameOrDescendantMountPath(
            item.mountMeta.normalizedPath,
            entry.normalized_path,
          ),
      )
    ) {
      return false;
    }
    return true;
  });

  const movePreflight: MountMovePreflightResult = destinationEntries
    ? resolveMountMovePreflight({
        items,
        targetPath: currentPath,
        destinationEntries,
      })
    : { ok: false, code: "unsupported_selection" };

  return {
    childFolders,
    movePreflightError: movePreflight.ok ? null : movePreflight,
    canSubmit: !isLoading && !isError && Boolean(destinationEntries) && movePreflight.ok,
  };
};
