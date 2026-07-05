import { Item } from "@/features/drivers/types";

export const flattenBrowsePages = <TPage, TItem extends Item>(
  pages: TPage[] | undefined,
  mapPageItems: (page: TPage) => TItem[],
): TItem[] => {
  return pages?.flatMap((page) => mapPageItems(page)) ?? [];
};
