import { ItemType, LinkReach } from "@/features/drivers/types";

import {
  buildSdkExplorerRedirectUrl,
  canPickSdkItem,
  getSdkChooseUpdates,
  resolveSdkLandingAction,
} from "../sdkRuntime";

describe("sdkRuntime", () => {
  it("allows picking files that are already public or updatable", () => {
    expect(
      canPickSdkItem({
        abilities: { update: false },
        link_reach: LinkReach.PUBLIC,
        type: ItemType.FILE,
      } as never),
    ).toBe(true);
    expect(
      canPickSdkItem({
        abilities: { update: true },
        link_reach: LinkReach.RESTRICTED,
        type: ItemType.FILE,
      } as never),
    ).toBe(true);
    expect(
      canPickSdkItem({
        abilities: { update: true },
        link_reach: LinkReach.RESTRICTED,
        type: ItemType.FOLDER,
      } as never),
    ).toBe(false);
  });

  it("builds the SDK explorer redirect URL", () => {
    expect(buildSdkExplorerRedirectUrl(null)).toBe("/sdk/explorer");
    expect(buildSdkExplorerRedirectUrl("save")).toBe("/sdk/explorer?mode=save");
  });

  it("resolves the landing action for missing token, redirect and login", () => {
    expect(
      resolveSdkLandingAction({
        currentHref: "http://app.example.test/sdk?token=a",
        mode: null,
        token: null,
        user: null,
      }),
    ).toEqual({ kind: "missing_token" });
    expect(
      resolveSdkLandingAction({
        currentHref: "http://app.example.test/sdk?token=a",
        mode: "save",
        token: "sdk-token",
        user: { id: "user-1" },
      }),
    ).toEqual({ kind: "redirect", mode: "save", token: "sdk-token" });
    expect(
      resolveSdkLandingAction({
        currentHref: "http://app.example.test/sdk?token=a",
        mode: null,
        token: "sdk-token",
        user: null,
      }),
    ).toEqual({
      kind: "login",
      returnTo: "http://app.example.test/sdk?token=a",
      token: "sdk-token",
    });
  });

  it("returns only the public-link upgrades that are actually required", () => {
    expect(
      getSdkChooseUpdates([
        { id: "file-1", link_reach: LinkReach.PUBLIC } as never,
        { id: "file-2", link_reach: LinkReach.RESTRICTED } as never,
      ]),
    ).toEqual([
      {
        id: "file-2",
        link_reach: LinkReach.PUBLIC,
        link_role: "reader",
      },
    ]);
  });
});
