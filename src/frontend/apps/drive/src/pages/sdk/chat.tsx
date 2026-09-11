import SuiteFilePicker from "@/features/sdk/SuiteFilePicker";

export default function ChatPicker() {
  return <SuiteFilePicker consumer="chat" />;
}
ChatPicker.getLayout = SuiteFilePicker.getLayout;
