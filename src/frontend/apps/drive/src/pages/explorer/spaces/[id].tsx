import { useRouter } from "next/router";
import { SpacesExplorer } from "@/features/storage/SpacesExplorer";
import { getGlobalExplorerLayout } from "@/features/layouts/components/explorer/ExplorerLayout";

export default function SpacePage() {
  const { query } = useRouter();
  return (
    <SpacesExplorer
      spaceId={typeof query.id === "string" ? query.id : undefined}
    />
  );
}
SpacePage.getLayout = getGlobalExplorerLayout;
