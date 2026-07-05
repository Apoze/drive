import { MountEntryAbilities, MountEntryType } from "@/features/drivers/types";

export type MountShellActionId =
  | "import_files"
  | "import_folders"
  | "create_folder";

type MountShellActionContext = {
  capabilities: Record<string, boolean>;
  entry: {
    entry_type: MountEntryType;
    abilities: MountEntryAbilities;
  };
};

export const getMountShellActionIds = (
  browse?: MountShellActionContext | null,
): MountShellActionId[] => {
  if (!browse || browse.entry.entry_type !== "folder") {
    return [];
  }

  const actionIds: MountShellActionId[] = [];

  if (
    browse.capabilities["mount.create_folder"] &&
    browse.entry.abilities.create_folder
  ) {
    actionIds.push("create_folder");
  }

  if (browse.capabilities["mount.upload"] && browse.entry.abilities.upload) {
    actionIds.push("import_files");
  }

  if (
    browse.capabilities["mount.upload"] &&
    browse.entry.abilities.upload &&
    browse.capabilities["mount.create_folder"] &&
    browse.entry.abilities.create_folder
  ) {
    actionIds.push("import_folders");
  }

  return actionIds;
};
