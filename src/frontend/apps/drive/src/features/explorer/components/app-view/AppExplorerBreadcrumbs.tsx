import React from "react";
import { Button, useModal } from "@gouvfr-lasuite/cunningham-react";
import {
  NavigationEventType,
  useGlobalExplorer,
} from "@/features/explorer/components/GlobalExplorerContext";
import {
  HorizontalSeparator,
  IconSize,
  useDropdownMenu,
} from "@gouvfr-lasuite/ui-kit";
import { WorkspaceIcon } from "@/features/explorer/components/icons/ItemIcon";
import createFolderSvg from "@/assets/icons/add_folder.svg";
import { EmbeddedExplorerGridBreadcrumbs } from "@/features/explorer/components/embedded-explorer/EmbeddedExplorerGridBreadcrumbs";
import { ExplorerCreateFolderModal } from "../modals/ExplorerCreateFolderModal";
import { ImportDropdown } from "../item-actions/ImportDropdown";
import { useTranslation } from "react-i18next";
import { useRouter } from "next/router";
import { useBreadcrumbQuery } from "../../hooks/useBreadcrumb";
import { useMemo } from "react";
import { useEntitlementsQuery } from "@/features/entitlements/useEntitlementsQuery";
import { addToast, ToasterItem } from "@/features/ui/components/toaster/Toaster";
import {
  getDefaultRouteDataByPath,
  getMobileBreadcrumbState,
  resolveMobileBreadcrumbBackTarget,
  shouldShowAppBreadcrumbActions,
} from "./explorerTopBarHelpers";

export const AppExplorerBreadcrumbs = () => {
  const { item, onNavigate } = useGlobalExplorer();
  const router = useRouter();
  const { t } = useTranslation();
  const createFolderModal = useModal();
  const importDropdown = useDropdownMenu();
  const { data: entitlements } = useEntitlementsQuery();
  const canUpload = entitlements?.can_upload?.result ?? true;
  const cannotUploadMessage =
    entitlements?.can_upload?.message || t("entitlements.can_upload.cannot_upload");

  const showActions = shouldShowAppBreadcrumbActions({
    pathname: router.pathname,
    item,
  });

  if (!item && !getDefaultRouteDataByPath(router.pathname)) {
    return null;
  }

  return (
    <>
      <div className="explorer__content__breadcrumbs">
        <EmbeddedExplorerGridBreadcrumbs
          currentItemId={item?.id}
          item={item}
          showMenuLastItem={true}
          onGoBack={(item) => {
            onNavigate({
              type: NavigationEventType.ITEM,
              item,
            });
          }}
        />

        {showActions && (
          <div className="explorer__content__breadcrumbs__actions">
            {canUpload ? (
              <ImportDropdown
                importMenu={importDropdown}
                trigger={
                  <Button
                    variant="tertiary"
                    size="small"
                    onClick={() => {
                      importDropdown.setIsOpen(true);
                    }}
                  >
                    {t("explorer.tree.import.label")}
                  </Button>
                }
              />
            ) : (
              <Button
                variant="tertiary"
                size="small"
                onClick={() => {
                  addToast(
                    <ToasterItem type="error">
                      <span>{cannotUploadMessage}</span>
                    </ToasterItem>,
                  );
                }}
              >
                {t("explorer.tree.import.label")}
              </Button>
            )}
            <Button
              icon={<img src={createFolderSvg.src} alt="Create Folder" />}
              variant="tertiary"
              data-testid="create-folder-button"
              size="small"
              onClick={() => {
                createFolderModal.open();
              }}
            />
          </div>
        )}
      </div>
      <div className="explorer__content__separator">
        <HorizontalSeparator withPadding={false} />
      </div>
      <ExplorerCreateFolderModal {...createFolderModal} parentId={item?.id} />
    </>
  );
};

export const ExplorerBreadcrumbsMobile = () => {
  const router = useRouter();
  const { t } = useTranslation();
  const { item, onNavigate } = useGlobalExplorer();
  const { data: breadcrumb } = useBreadcrumbQuery(item?.id);

  const defaultRouteData = getDefaultRouteDataByPath(router.pathname);
  const items = useMemo(() => getMobileBreadcrumbState(breadcrumb), [breadcrumb]);

  if (!item && defaultRouteData) {
    return (
      <div className="explorer__content__breadcrumbs--mobile">
        <div className="explorer__content__breadcrumbs--mobile__default-route">
          <defaultRouteData.icon size={IconSize.MEDIUM} />

          {t(defaultRouteData.label)}
        </div>
      </div>
    );
  }

  if (!items) {
    return null;
  }

  const { workspace, parent, current, isRoot } = items;

  const workspaceTitle = workspace.main_workspace
    ? t("explorer.workspaces.mainWorkspace")
    : workspace.title;
  return (
    <div className="explorer__content__breadcrumbs--mobile">
      {isRoot ? (
        <div className="explorer__content__breadcrumbs--mobile__workspace">
          <WorkspaceIcon
            isMainWorkspace={workspace.main_workspace}
            iconSize={IconSize.X_SMALL}
          />
          <span>{workspaceTitle}</span>
        </div>
      ) : (
        <div className="explorer__content__breadcrumbs--mobile__container">
          <div className="explorer__content__breadcrumbs--mobile__container__actions">
            <Button
              variant="bordered"
              color="neutral"
              icon={<span className="material-icons">chevron_left</span>}
              onClick={() => {
                const backTarget = resolveMobileBreadcrumbBackTarget(parent?.id);
                if (backTarget) {
                  router.push(backTarget);
                } else {
                  onNavigate({
                    type: NavigationEventType.ITEM,
                    item: parent,
                  });
                }
              }}
            />
          </div>
          <div className="explorer__content__breadcrumbs--mobile__container__info">
            <div className="explorer__content__breadcrumbs--mobile__container__info__title">
              <WorkspaceIcon
                isMainWorkspace={workspace.main_workspace}
                iconSize={IconSize.X_SMALL}
              />
              <span>{workspaceTitle}</span>
            </div>
            <div className="explorer__content__breadcrumbs--mobile__container__info__folder">
              {current.title}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
