import { getGlobalExplorerLayout } from "@/features/layouts/components/explorer/ExplorerLayout";
import { TransferHistory } from "@/features/storage/TransferHistory";

export default function TransfersPage() {
  return <TransferHistory />;
}
TransfersPage.getLayout = getGlobalExplorerLayout;
