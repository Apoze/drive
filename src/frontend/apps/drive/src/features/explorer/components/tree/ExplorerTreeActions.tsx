import React from "react";
import { DropdownMenu, useDropdownMenu } from "@gouvfr-lasuite/ui-kit";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { useTranslation } from "react-i18next";

import { ExplorerSearchButton } from "@/features/explorer/components/app-view/ExplorerSearchButton";
import { useGlobalExplorer } from "@/features/explorer/components/GlobalExplorerContext";
import { useCreateMenuItems } from "../../hooks/useCreateMenuItems";

/**
 * Hybrid (Option 3):
 * - Upstream structure: create actions + modals come from useCreateMenuItems.
 * - Fork UX preserved: menu includes "Plus de formats…" via the hook.
 */
export const ExplorerTreeActions = () => {
  const { t } = useTranslation();
  const { treeIsInitialized } = useGlobalExplorer();

  const createMenu = useDropdownMenu();
  const { menuItems, modals } = useCreateMenuItems();

  if (!treeIsInitialized) {
    return null;
  }

  return (
    <>
      <div className="explorer__tree__actions">
        <div className="explorer__tree__actions__left">
          <DropdownMenu
            options={menuItems}
            {...createMenu}
            onOpenChange={createMenu.setIsOpen}
          >
            <Button
              icon={<span className="material-icons">add</span>}
              onClick={() => createMenu.setIsOpen(true)}
            >
              {t("explorer.tree.createFolder")}
            </Button>
          </DropdownMenu>
        </div>
        <ExplorerSearchButton keyboardShortcut />
      </div>
      {modals}
    </>
  );
};
