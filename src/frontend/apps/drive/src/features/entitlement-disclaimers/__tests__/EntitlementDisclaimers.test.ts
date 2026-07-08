import {
  EntitlementCanUploadReasons,
  Entitlements,
} from "@/features/drivers/Driver";
import { ApiConfig } from "@/features/drivers/types";

import {
  getActiveEntitlementDisclaimers,
  storageKey,
} from "../EntitlementDisclaimers";

const makeStorage = (initialValues: Record<string, string> = {}) => {
  const values = new Map(Object.entries(initialValues));

  return {
    getItem: jest.fn((key: string) => values.get(key) ?? null),
    removeItem: jest.fn((key: string) => {
      values.delete(key);
    }),
    setItem: jest.fn((key: string, value: string) => {
      values.set(key, value);
    }),
  };
};

const makeEntitlements = (
  canUpload: Entitlements["can_upload"],
): Entitlements => ({
  can_access: { result: true },
  can_upload: canUpload,
  context: {},
});

const config: ApiConfig["FRONTEND_ENTITLEMENTS_DISCLAIMERS"] = {
  cannot_upload: {
    enabled: true,
    showPotentialOperators: false,
  },
};

describe("getActiveEntitlementDisclaimers", () => {
  it("activates cannot-upload once when upload is denied for a configured reason", () => {
    const storage = makeStorage();
    const activeDisclaimers = getActiveEntitlementDisclaimers(
      config,
      makeEntitlements({
        result: false,
        reason: EntitlementCanUploadReasons.NOT_ACTIVATED,
      }),
      storage,
    );

    expect(activeDisclaimers).toHaveLength(1);
    expect(activeDisclaimers[0].name).toBe("cannot_upload");
    expect(storage.setItem).toHaveBeenCalledWith(
      storageKey("cannot_upload"),
      "1",
    );
  });

  it("does not activate cannot-upload again while the seen flag is present", () => {
    const storage = makeStorage({ [storageKey("cannot_upload")]: "1" });
    const activeDisclaimers = getActiveEntitlementDisclaimers(
      config,
      makeEntitlements({
        result: false,
        reason: EntitlementCanUploadReasons.NO_ORGANIZATION,
      }),
      storage,
    );

    expect(activeDisclaimers).toHaveLength(0);
    expect(storage.setItem).not.toHaveBeenCalled();
    expect(storage.removeItem).not.toHaveBeenCalled();
  });

  it("clears the seen flag when the denied-upload reason no longer applies", () => {
    const storage = makeStorage({ [storageKey("cannot_upload")]: "1" });
    const activeDisclaimers = getActiveEntitlementDisclaimers(
      config,
      makeEntitlements({ result: true }),
      storage,
    );

    expect(activeDisclaimers).toHaveLength(0);
    expect(storage.removeItem).toHaveBeenCalledWith(
      storageKey("cannot_upload"),
    );
  });

  it("clears the seen flag when the disclaimer is disabled in config", () => {
    const storage = makeStorage({ [storageKey("cannot_upload")]: "1" });
    const activeDisclaimers = getActiveEntitlementDisclaimers(
      {
        cannot_upload: {
          enabled: false,
        },
      },
      makeEntitlements({
        result: false,
        reason: EntitlementCanUploadReasons.NOT_ACTIVATED,
      }),
      storage,
    );

    expect(activeDisclaimers).toHaveLength(0);
    expect(storage.removeItem).toHaveBeenCalledWith(
      storageKey("cannot_upload"),
    );
  });
});
