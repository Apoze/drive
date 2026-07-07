import { Item } from "@/features/drivers/types";
import { useTransientItemsPoller } from "./useTransientItemsPoller";

export const useDuplicatingItemsPoller = (items: Item[]) => {
  useTransientItemsPoller(items);
};
