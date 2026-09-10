import { StorageAdmin } from "@/features/storage/StorageAdmin";
import { getGlobalExplorerLayout } from "@/features/layouts/components/explorer/ExplorerLayout";
export default function StorageAdministrationPage() {
  return <StorageAdmin />;
}
StorageAdministrationPage.getLayout = getGlobalExplorerLayout;
