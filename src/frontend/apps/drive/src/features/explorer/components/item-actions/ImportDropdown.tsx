import React from "react";
import { DropdownMenu, useDropdownMenu } from "@gouvfr-lasuite/ui-kit";
import { useTranslation } from "react-i18next";
import { buildItemImportMenuItems } from "./itemImportMenuItems";
export type ImportDropdownProps = {
  trigger: React.ReactNode;
  importMenu: ReturnType<typeof useDropdownMenu>;
};

export const ImportDropdown = ({
  trigger,
  importMenu,
}: ImportDropdownProps) => {
  const { t } = useTranslation();
  return (
    <DropdownMenu
      options={buildItemImportMenuItems({ t })}
      {...importMenu}
      onOpenChange={importMenu.setIsOpen}
    >
      {trigger}
    </DropdownMenu>
  );
};
