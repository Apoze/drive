import React from "react";
import { errorToString } from "@/features/api/APIError";
import { getDriver } from "@/features/config/Config";
import { writeTextToClipboard } from "@/hooks/useCopyToClipboard";
import {
  addToast,
  ToasterItem,
} from "@/features/ui/components/toaster/Toaster";
import { MountExplorerItem } from "./mountExplorerItems";

export const createAndCopyMountShareLink = async (
  item: MountExplorerItem,
) => {
  try {
    const response = await getDriver().createMountShareLink({
      mountId: item.mountMeta.mountId,
      path: item.mountMeta.normalizedPath,
    });

    try {
      await writeTextToClipboard(response.share_url);
      addToast(
        <ToasterItem>
          <span className="material-icons">check</span>
          <span>{response.share_url}</span>
        </ToasterItem>,
      );
    } catch {
      addToast(
        <ToasterItem type="error">
          <span className="material-icons">error</span>
          <span>{response.share_url}</span>
        </ToasterItem>,
      );
    }
  } catch (error) {
    addToast(
      <ToasterItem type="error">{errorToString(error)}</ToasterItem>,
    );
  }
};
