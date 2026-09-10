import React from "react";
import Router from "next/router";
import { getRuntimeConfig } from "@/features/config/runtimeConfig";
import { resolveLegacyMount } from "@/features/storage/api";
import { errorToString } from "@/features/api/APIError";
import { getDriver } from "@/features/config/Config";
import { writeTextToClipboard } from "@/hooks/useCopyToClipboard";
import {
  addToast,
  ToasterItem,
} from "@/features/ui/components/toaster/Toaster";
import { MountExplorerItem } from "./mountExplorerItems";

export const createAndCopyMountShareLink = async (item: MountExplorerItem) => {
  try {
    if (getRuntimeConfig()?.STORAGE_UNIFIED_ENABLED) {
      const target = await resolveLegacyMount(
        item.mountMeta.mountId,
        item.mountMeta.normalizedPath,
      );
      await Router.push(
        `${target.href}${target.href.includes("?") ? "&" : "?"}share=true`,
      );
      return;
    }
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
    addToast(<ToasterItem type="error">{errorToString(error)}</ToasterItem>);
  }
};
