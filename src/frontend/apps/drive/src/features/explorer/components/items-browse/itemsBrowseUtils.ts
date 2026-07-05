import { PaginatedChildrenResult } from "@/features/drivers/Driver";

export const mapItemsBrowsePageItems = (page: PaginatedChildrenResult) =>
  page.children;
