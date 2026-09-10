import SuiteFilePicker from "@/features/sdk/SuiteFilePicker";

export default function ProjectsPicker() {
  return <SuiteFilePicker consumer="projects" />;
}
ProjectsPicker.getLayout = SuiteFilePicker.getLayout;
