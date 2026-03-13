import { useMemo } from "react";
import { useRouter } from "next/router";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { HorizontalSeparator, IconSize } from "@gouvfr-lasuite/ui-kit";
import { useTranslation } from "react-i18next";
import {
  BreadcrumbItemButton,
} from "@/features/explorer/components/embedded-explorer/EmbeddedExplorerGridBreadcrumbs";
import { MountsIcon } from "@/features/ui/components/icon/MountsIcon";
import { Breadcrumbs } from "@/features/ui/components/breadcrumbs/Breadcrumbs";

type MountExplorerBreadcrumbsProps = {
  mountTitle?: string;
  normalizedPath?: string;
  actions?: React.ReactNode;
  onNavigateToPath?: (path: string) => void;
};

export const MountExplorerBreadcrumbs = ({
  mountTitle,
  normalizedPath,
  actions,
  onNavigateToPath,
}: MountExplorerBreadcrumbsProps) => {
  const router = useRouter();
  const { t } = useTranslation();

  const items = useMemo(() => {
    const breadcrumbItems = [
      {
        content: (
          <div
            className="c__breadcrumbs__button"
            data-testid="default-route-button"
            role="button"
            tabIndex={0}
            onClick={() => {
              void router.push("/explorer/mounts");
            }}
          >
            <MountsIcon size={IconSize.MEDIUM} />
            {t("explorer.tree.mounts")}
          </div>
        ),
      },
    ];

    if (!mountTitle) {
      return breadcrumbItems;
    }

    breadcrumbItems.push({
      content: (
        <BreadcrumbItemButton
          item={{
            id: `${mountTitle}-root`,
            title: mountTitle,
            path: "/",
            depth: 0,
            main_workspace: false,
          }}
          isActive={!normalizedPath || normalizedPath === "/"}
          onClick={() => onNavigateToPath?.("/")}
        />
      ),
    });

    const segments = (normalizedPath ?? "/").split("/").filter(Boolean);
    let currentPath = "";

    segments.forEach((segment, index) => {
      currentPath = `${currentPath}/${segment}`;
      const isActive = index === segments.length - 1;
      breadcrumbItems.push({
        content: (
          <BreadcrumbItemButton
            item={{
              id: currentPath,
              title: segment,
              path: currentPath,
              depth: index + 1,
              main_workspace: false,
            }}
            isActive={isActive}
            onClick={() => onNavigateToPath?.(currentPath)}
          />
        ),
      });
    });

    return breadcrumbItems;
  }, [mountTitle, normalizedPath, onNavigateToPath, router, t]);

  return (
    <>
      <div className="explorer__content__breadcrumbs">
        <Breadcrumbs items={items} />
        {actions && (
          <div className="explorer__content__breadcrumbs__actions">
            {actions}
          </div>
        )}
      </div>
      <div className="explorer__content__separator">
        <HorizontalSeparator withPadding={false} />
      </div>
    </>
  );
};

type MountExplorerPrimaryActionProps = {
  label: string;
  onClick: () => void;
  disabled?: boolean;
};

export const MountExplorerPrimaryAction = ({
  label,
  onClick,
  disabled,
}: MountExplorerPrimaryActionProps) => {
  return (
    <Button variant="tertiary" size="small" onClick={onClick} disabled={disabled}>
      {label}
    </Button>
  );
};
