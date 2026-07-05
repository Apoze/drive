import { MOUNT_CAPABILITY_KEYS } from "../constants";

describe("mounts/constants", () => {
  it("keeps the stable ordered capability contract", () => {
    expect(MOUNT_CAPABILITY_KEYS).toEqual([
      "mount.create_folder",
      "mount.upload",
      "mount.duplicate",
      "mount.preview",
      "mount.wopi",
      "mount.share_link",
    ]);
  });
});
