import React from "react";
import ResourcePage from "../resources/[id]";
import { useConfig } from "@/features/config/ConfigProvider";
import { ItemsBrowseExplorer } from "@/features/explorer/components/items-browse/ItemsBrowseExplorer";
import { getGlobalExplorerLayout } from "@/features/layouts/components/explorer/ExplorerLayout";
import { useRouter } from "next/router";

export default function ItemPage() {
  const router = useRouter();
  const { config } = useConfig();
  const itemId = typeof router.query.id === "string" ? router.query.id : null;

  if (config.STORAGE_UNIFIED_ENABLED) return <ResourcePage />;

  return (
    <ItemsBrowseExplorer
      kind="children"
      itemId={itemId}
      viewConfigKey="folder"
      navigationId={itemId ?? undefined}
    />
  );
}

ItemPage.getLayout = getGlobalExplorerLayout;
