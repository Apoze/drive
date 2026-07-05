import React from "react";
import { Button, useModal } from "@gouvfr-lasuite/cunningham-react";
import { ExplorerSearchModal } from "@/features/explorer/components/modals/search/ExplorerSearchModal";
import { useTranslation } from "react-i18next";
import { useEffect } from "react";
import { ItemFilters } from "@/features/drivers/Driver";
import { isExplorerSearchShortcut } from "./searchEntrypointHelpers";
export const ExplorerSearchButton = ({
  keyboardShortcut,
  defaultFilters,
}: {
  keyboardShortcut?: boolean;
  defaultFilters?: ItemFilters;
}) => {
  const searchModal = useModal();
  const { t } = useTranslation();

  // Toggle the menu when ⌘K is pressed
  useEffect(() => {
    if (!keyboardShortcut) {
      return;
    }
    const down = (e: KeyboardEvent) => {
      if (isExplorerSearchShortcut(e)) {
        e.preventDefault();
        searchModal.open();
      }
    };

    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, [keyboardShortcut, searchModal]);

  return (
    <>
      <ExplorerSearchModal {...searchModal} defaultFilters={defaultFilters} />

      <Button
        variant="tertiary"
        aria-label={t("explorer.tree.search")}
        icon={<span className="material-icons">search</span>}
        onClick={searchModal.open}
      />
    </>
  );
};
