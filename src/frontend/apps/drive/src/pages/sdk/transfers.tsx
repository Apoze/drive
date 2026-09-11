import SuiteFilePicker from "@/features/sdk/SuiteFilePicker";

export default function TransfersPicker() {
  return <SuiteFilePicker consumer="transfers" />;
}
TransfersPicker.getLayout = SuiteFilePicker.getLayout;
