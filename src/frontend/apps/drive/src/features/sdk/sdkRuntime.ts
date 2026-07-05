import { Item, ItemType, LinkReach, LinkRole } from "@/features/drivers/types";

export const canPickSdkItem = (item: Item) => {
  if (item.type !== ItemType.FILE) {
    return false;
  }
  if (item.link_reach === LinkReach.PUBLIC) {
    return true;
  }
  if (item.abilities?.update) {
    return true;
  }
  return false;
};

export const buildSdkExplorerRedirectUrl = (mode: string | null) => {
  let url = "/sdk/explorer";
  if (mode) {
    url += `?mode=${mode}`;
  }
  return url;
};

export const resolveSdkLandingAction = ({
  currentHref,
  mode,
  token,
  user,
}: {
  currentHref: string;
  mode: string | null;
  token: string | null;
  user?: unknown;
}) => {
  if (!token) {
    return { kind: "missing_token" } as const;
  }
  if (user) {
    return { kind: "redirect", mode, token } as const;
  }
  return { kind: "login", returnTo: currentHref, token } as const;
};

export const getSdkChooseUpdates = (selectedItems: Item[]) => {
  return selectedItems.flatMap((item) => {
    if (item.link_reach === LinkReach.PUBLIC) {
      return [];
    }
    return [
      {
        id: item.id,
        link_reach: LinkReach.PUBLIC,
        link_role: LinkRole.READER,
      },
    ];
  });
};
