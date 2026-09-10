import React, { useMemo } from "react";
import Link from "next/link";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { HorizontalSeparator, IconSize } from "@gouvfr-lasuite/ui-kit";
import { useTranslation } from "react-i18next";
import { BreadcrumbItemButton } from "@/features/explorer/components/embedded-explorer/EmbeddedExplorerGridBreadcrumbs";
import { MountsIcon } from "@/features/ui/components/icon/MountsIcon";
import { Breadcrumbs } from "@/features/ui/components/breadcrumbs/Breadcrumbs";

type MountExplorerBreadcrumbsProps = {
  unified?: boolean;
  mountTitle?: string;
  normalizedPath?: string;
  actions?: React.ReactNode;
  onNavigateToPath?: (path: string) => void;
};

export const MountExplorerBreadcrumbs = ({
  unified = false,
  mountTitle,
  normalizedPath,
  actions,
  onNavigateToPath,
}: MountExplorerBreadcrumbsProps) => {
  const { t } = useTranslation();

  const items = useMemo(() => {
    const breadcrumbItems = [
      {
        content: (
          <Link
            className="c__breadcrumbs__button"
            data-testid="default-route-button"
            title={t(unified ? "storage.spaces" : "explorer.tree.mounts")}
            href={unified ? "/explorer/items/my-files" : "/explorer/mounts"}
          >
            <MountsIcon size={IconSize.MEDIUM} />
            <span className="c__breadcrumbs__button__label">
              {t(unified ? "storage.spaces" : "explorer.tree.mounts")}
            </span>
          </Link>
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
      const pathForSegment = currentPath;
      const isActive = index === segments.length - 1;
      breadcrumbItems.push({
        content: (
          <BreadcrumbItemButton
            item={{
              id: pathForSegment,
              title: segment,
              path: pathForSegment,
              depth: index + 1,
              main_workspace: false,
            }}
            isActive={isActive}
            onClick={() => onNavigateToPath?.(pathForSegment)}
          />
        ),
      });
    });

    return breadcrumbItems;
  }, [mountTitle, normalizedPath, onNavigateToPath, unified, t]);

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
    <Button
      variant="tertiary"
      size="small"
      onClick={onClick}
      disabled={disabled}
    >
      {label}
    </Button>
  );
};
