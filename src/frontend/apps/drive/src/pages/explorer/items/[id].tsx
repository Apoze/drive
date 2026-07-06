import React from "react";
import { ItemsBrowseExplorer } from "@/features/explorer/components/items-browse/ItemsBrowseExplorer";
import { getGlobalExplorerLayout } from "@/features/layouts/components/explorer/ExplorerLayout";
import { useRouter } from "next/router";
export default function ItemPage() {
  const router = useRouter();
  const itemId = typeof router.query.id === "string" ? router.query.id : null;

  return <ItemsBrowseExplorer kind="children" itemId={itemId} />;
}

ItemPage.getLayout = getGlobalExplorerLayout;
