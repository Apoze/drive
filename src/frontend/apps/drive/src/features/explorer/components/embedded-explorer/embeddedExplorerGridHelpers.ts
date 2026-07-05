import { Item, ItemType } from "@/features/drivers/types";
import { canMountItemReceiveDrop } from "@/features/mounts/utils/mountDnd";

export const isEmbeddedExplorerGridDropDisabled = ({
  item,
  isSelected,
}: {
  item: Item;
  isSelected: boolean;
}) => {
  return (
    isSelected ||
    item.type !== ItemType.FOLDER ||
    (!item.abilities?.children_create && !canMountItemReceiveDrop(item))
  );
};
