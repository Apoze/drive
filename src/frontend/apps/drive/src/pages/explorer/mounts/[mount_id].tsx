import React from "react";
import { MountBrowseExplorer } from "@/features/mounts/components/MountBrowseExplorer";
import { getGlobalExplorerLayout } from "@/features/layouts/components/explorer/ExplorerLayout";

export default function MountBrowsePage() {
  return <MountBrowseExplorer />;
}

MountBrowsePage.getLayout = getGlobalExplorerLayout;
