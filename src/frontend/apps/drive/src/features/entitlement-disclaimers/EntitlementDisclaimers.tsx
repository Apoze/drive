import { EntitlementDisclaimerModal } from "./components/EntitlementDisclaimerModal";
import CannotUploadDisclaimer from "./disclaimers/CannotUploadDisclaimer";
import { EntitlementDisclaimer } from "./types";
import { useEffect, useState } from "react";
import { useEntitlements } from "./hooks/useEntitlements";
import { useConfig } from "../config/ConfigProvider";
import { Entitlements } from "../drivers/Driver";
import { ApiConfig } from "../drivers/types";

export const storageKey = (name: string) =>
  `entitlement-disclaimer-seen:${name}`;

const DISCLAIMER_REGISTRY = [CannotUploadDisclaimer];

const DISCLAIMER_REGISTRY_MAP = DISCLAIMER_REGISTRY.reduce(
  (acc, disclaimer) => {
    acc[disclaimer.name] = disclaimer;
    return acc;
  },
  {} as Record<
    keyof NonNullable<ApiConfig["FRONTEND_ENTITLEMENTS_DISCLAIMERS"]>,
    EntitlementDisclaimer
  >,
);

type EntitlementDisclaimerStorage = Pick<
  Storage,
  "getItem" | "removeItem" | "setItem"
>;

export const getActiveEntitlementDisclaimers = (
  config: ApiConfig["FRONTEND_ENTITLEMENTS_DISCLAIMERS"],
  entitlements: Entitlements,
  storage: EntitlementDisclaimerStorage = localStorage,
) => {
  const activeDisclaimers = [] as EntitlementDisclaimer[];

  Object.entries(DISCLAIMER_REGISTRY_MAP).forEach(([name, disclaimer]) => {
    const key = storageKey(name);
    // Disabled in config?
    if (
      config?.[name as keyof NonNullable<typeof config>]?.enabled !== true
    ) {
      storage.removeItem(key);
      return;
    }
    const show = disclaimer.show(entitlements);
    // Already seen.
    if (storage.getItem(key)) {
      if (!show) {
        // Clear seen flag. So on next change, the disclaimer will be shown again.
        storage.removeItem(key);
      }
      return;
    }
    // Should not be shown.
    if (!show) {
      return;
    }
    // Should be shown.
    storage.setItem(key, "1");
    activeDisclaimers.push(disclaimer);
  });

  return activeDisclaimers;
};

export const EntitlementDisclaimers = () => {
  const { config } = useConfig();
  const { data: entitlements } = useEntitlements();
  const [activeDisclaimers, setActiveDisclaimers] =
    useState<EntitlementDisclaimer[]>();

  /**
   * Compute active disclaimers.
   */
  useEffect(() => {
    if (!entitlements) {
      return;
    }
    setActiveDisclaimers(
      getActiveEntitlementDisclaimers(
        config.FRONTEND_ENTITLEMENTS_DISCLAIMERS,
        entitlements,
      ),
    );
  }, [config.FRONTEND_ENTITLEMENTS_DISCLAIMERS, entitlements]);

  if (!entitlements) {
    return null;
  }

  return (
    <>
      {activeDisclaimers?.map((disclaimer) => {
        const { title, description } = disclaimer.render(
          config.FRONTEND_ENTITLEMENTS_DISCLAIMERS?.[disclaimer.name],
          entitlements,
        );
        return (
          <EntitlementDisclaimerModal
            key={disclaimer.name}
            title={title}
            description={description}
          />
        );
      })}
    </>
  );
};
