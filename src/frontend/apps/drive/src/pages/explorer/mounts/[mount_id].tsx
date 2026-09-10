import { useConfig } from "@/features/config/ConfigProvider";
import { LegacyStorageRoute } from "@/features/storage/LegacyStorageRoute";
import React from "react";
import { MountBrowseExplorer } from "@/features/mounts/components/MountBrowseExplorer";
import { getGlobalExplorerLayout } from "@/features/layouts/components/explorer/ExplorerLayout";

export default function MountBrowsePage() {
  const { config } = useConfig();
  return config.STORAGE_UNIFIED_ENABLED ? (
    <LegacyStorageRoute />
  ) : (
    <LegacyMountBrowsePage />
  );
}

function LegacyMountBrowsePage() {
  return <MountBrowseExplorer />;
}

MountBrowsePage.getLayout = getGlobalExplorerLayout;
