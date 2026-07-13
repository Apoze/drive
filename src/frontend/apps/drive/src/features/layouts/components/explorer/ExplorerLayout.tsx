import React, { useMemo } from "react";
import { useAuth } from "@/features/auth/Auth";
import { useConfig } from "@/features/config/ConfigProvider";
import { ExplorerTree } from "@/features/explorer/components/tree/ExplorerTree";
import {
  HelpMenu,
  IconSize,
  MainLayout,
  StorageGaugeButton,
  StorageGaugeInformation,
  useResponsive,
} from "@gouvfr-lasuite/ui-kit";
import { Info, Warning } from "@gouvfr-lasuite/ui-kit/icons";
import {
  Button,
  Modal,
  ModalProps,
  ModalSize,
  ModalTab,
  Tooltip,
  useModal,
} from "@gouvfr-lasuite/cunningham-react";
import { HeaderIcon, HeaderRight } from "../header/Header";
import {
  GlobalExplorerProvider,
  NavigationEvent,
  useGlobalExplorer,
} from "@/features/explorer/components/GlobalExplorerContext";
import { ExplorerRightPanelContent } from "@/features/explorer/components/right-panel/ExplorerRightPanelContent";
import { GlobalLayout } from "../global/GlobalLayout";
import { LeftPanelMobile } from "../left-panel/LeftPanelMobile";
import { useRouter } from "next/router";
import { useSyncUserLanguage } from "../../hooks/useSyncUserLanguage";
import { Item } from "@/features/drivers/types";
import { ReleaseNoteAuto } from "@/features/ui/components/release-note";
import {
  formatSizeTo,
  setManualNavigationItemId,
} from "@/features/explorer/utils/utils";
import {
  buildExplorerLayoutNavigateTarget,
  resolveExplorerPanelsLayoutState,
} from "./explorerShellHelpers";
import { ColumnPreferencesProvider } from "@/features/explorer/hooks/useColumnPreferences";
import { EntitlementDisclaimers } from "@/features/entitlement-disclaimers/EntitlementDisclaimers";
import { useEntitlementsQuery } from "@/features/entitlements/useEntitlementsQuery";
import { useTranslation } from "react-i18next";
import i18n from "@/features/i18n/initI18n";
import { UserProfile } from "@/features/ui/components/user/UserProfile";
import { Gaufre } from "@/features/ui/components/gaufre/Gaufre";

export const getGlobalExplorerLayout = (page: React.ReactElement) => {
  return <GlobalExplorerLayout>{page}</GlobalExplorerLayout>;
};

export const GlobalExplorerLayout = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  return (
    <GlobalLayout>
      <ColumnPreferencesProvider>
        <ReleaseNoteAuto />
        <EntitlementDisclaimers />
        <ExplorerLayout>{children}</ExplorerLayout>
      </ColumnPreferencesProvider>
    </GlobalLayout>
  );
};

/**
 * This layout is used for the explorer page.
 * It is used to display the explorer tree and the header.
 */
export const ExplorerLayout = ({
  children,
}: {
  children: React.ReactNode;
  isMinimalLayout?: boolean;
}) => {
  const router = useRouter();

  const isMinimalLayout = router.query.minimal === "true";
  const itemId = router.query.id as string;
  const onNavigate = (e: NavigationEvent) => {
    // Only keep "minimal" in the query string so that when navigating, to keep the minimal layout on the next page
    // the minimal layout state is preserved; all other query params are dropped intentionally.
    const { minimal } = router.query;
    const item = e.item as Item;
    const navigationTarget = buildExplorerLayoutNavigateTarget({
      item,
      minimal,
    });
    // If the itemId is a favorite item, we need to get the favorite items. cf onLoadChildren in GlobalExplorerProvider.tsx
    const { id } = navigationTarget;
    setManualNavigationItemId(id);
    router.push(navigationTarget);
  };

  useSyncUserLanguage();

  return (
    <GlobalExplorerProvider
      itemId={itemId}
      displayMode="app"
      onNavigate={onNavigate}
    >
      <ExplorerPanelsLayout isMinimalLayout={isMinimalLayout}>
        {children}
      </ExplorerPanelsLayout>
    </GlobalExplorerProvider>
  );
};

export const ExplorerPanelsLayout = ({
  children,
  isMinimalLayout,
}: {
  children: React.ReactNode;
  isMinimalLayout?: boolean;
}) => {
  const {
    rightPanelOpen,
    setRightPanelOpen,
    item,
    rightPanelForcedItem: rightPanelItem,
    isLeftPanelOpen,
    setIsLeftPanelOpen,
  } = useGlobalExplorer();

  const { user } = useAuth();
  const panelsState = resolveExplorerPanelsLayoutState({
    hasUser: Boolean(user),
    isMinimalLayout,
  });

  return (
    <MainLayout
      enableResize
      rightPanelContent={<ExplorerRightPanelContent item={rightPanelItem} />}
      rightPanelIsOpen={rightPanelOpen}
      onToggleRightPanel={() => setRightPanelOpen(!rightPanelOpen)}
      leftPanelContent={
        panelsState.showExplorerTree ? <ExplorerTree /> : <LeftPanelMobile />
      }
      leftPanelFooter={<LeftPanelFooter />}
      isLeftPanelOpen={isLeftPanelOpen}
      hideLeftPanelOnDesktop={panelsState.hideLeftPanelOnDesktop}
      setIsLeftPanelOpen={() => setIsLeftPanelOpen(!isLeftPanelOpen)}
      icon={<HeaderIcon />}
      rightHeaderContent={
        <HeaderRight displaySearch={isMinimalLayout} currentItem={item} />
      }
    >
      {children}
    </MainLayout>
  );
};

const LeftPanelFooter = () => {
  const { isTablet } = useResponsive();
  const settingsModal = useModal();

  return (
    <>
      <div className="c__left-panel__footer__drive">
        {isTablet && (
          <>
            <UserProfile />
            <Gaufre />
          </>
        )}
        <HelpMenuButton />
        <LeftPanelFooterStorageGauge onClick={settingsModal.open} />
      </div>
      <SettingsModal {...settingsModal} />
    </>
  );
};

const HelpMenuButton = () => {
  const { config } = useConfig();
  const helpMenuConfig = config?.FRONTEND_HELP_MENU_CONFIG;
  if (!helpMenuConfig || Object.keys(helpMenuConfig).length === 0) {
    return null;
  }

  return (
    <HelpMenu
      documentationUrl={helpMenuConfig.documentationUrl}
      legal={helpMenuConfig.legal}
      onContactUs={
        helpMenuConfig.supportEmail
          ? () => window.open(helpMenuConfig.supportEmail)
          : undefined
      }
    />
  );
};

const SettingsModal = (props: Pick<ModalProps, "isOpen" | "onClose">) => {
  const { t } = useTranslation();
  const tabs: ModalTab[] = [
    {
      id: "storage",
      label: i18n.t("settings_modal.tabs.storage.title"),
      title: i18n.t("settings_modal.tabs.storage.title"),
      content: <SettingsModalStorageTab />,
    },
  ];

  return (
    <Modal
      variant="tab"
      size={ModalSize.LARGE}
      sidebarTitle={t("settings_modal.title")}
      tabs={tabs}
      constraints={{ preferredHeight: "500px" }}
      {...props}
    />
  );
};

const SettingsModalStorageTab = () => {
  const { config } = useConfig();
  const storageGauge = useStorageGauge();
  if (!storageGauge) {
    return null;
  }
  const informationLink = config?.FRONTEND_STORAGE_GAUGE_INFORMATION_LINK;
  return (
    <StorageGaugeInformation
      {...storageGauge}
      onMoreInfoClick={
        informationLink
          ? () => window.open(informationLink, "_blank")
          : undefined
      }
    />
  );
};

const LeftPanelFooterStorageGauge = (props: { onClick: () => void }) => {
  const storageGauge = useStorageGauge();
  if (!storageGauge) {
    return null;
  }
  return <StorageGaugeButton {...storageGauge} onClick={props.onClick} />;
};

const useStorageGauge = () => {
  const { data: entitlements } = useEntitlementsQuery();
  const { t } = useTranslation();

  return useMemo(() => {
    const quota = entitlements?.quota;
    if (!quota) {
      return null;
    }
    if (quota.state === "default") {
      return {
        quota,
        used: formatSizeTo(quota.usage!, "GB"),
        total: formatSizeTo(quota.limit!, "GB"),
      };
    }
    if (quota.state === "excedeed_locked") {
      return {
        quota,
        used: 0,
        total: 0,
        locked: true,
        lockedContent: (
          <span className="c__storage-gauge__locked-content">
            <Warning size={IconSize.SMALL} />{" "}
            {t(
              `quota.gauge.exceeded_locked.reason.${quota.reason}.description`,
            )}
          </span>
        ),
        title: t("quota.gauge.exceeded_locked.title"),
        label: t("quota.gauge.exceeded_locked.label"),
      };
    }
    if (quota.state === "error") {
      const error = quota.error ?? "";
      const errorTooltip = t("quota.gauge.error.tooltip", { error });
      return {
        quota,
        used: 0,
        total: 0,
        locked: true,
        lockedContent: (
          <Tooltip content={errorTooltip}>
            <span className="c__storage-gauge__locked-content">
              <Warning size={IconSize.SMALL} /> {t("quota.gauge.error.title")}
            </span>
          </Tooltip>
        ),
        title: t("quota.gauge.error.title"),
        label: t("quota.gauge.error.label"),
        labelChildren: (
          <Tooltip content={errorTooltip}>
            <Button
              icon={<Info size={IconSize.SMALL} />}
              size="nano"
              color="neutral"
              variant="tertiary"
            />
          </Tooltip>
        ),
      };
    }
    return null;
  }, [entitlements, t]);
};
