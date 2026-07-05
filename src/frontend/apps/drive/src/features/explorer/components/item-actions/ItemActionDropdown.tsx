import React from "react";
import { Item } from "@/features/drivers/types";
import { DropdownMenu, MenuItem } from "@gouvfr-lasuite/ui-kit";
import { useItemActionMenuItems } from "../../hooks/useItemActionMenuItems";

export type ItemActionDropdownProps = {
  item: Item;
  itemId?: string;
  isOpen: boolean;
  setIsOpen: (isOpen: boolean) => void;
  trigger: React.ReactNode;
  onModalOpenChange?: (isModalOpen: boolean) => void;
  minimal?: boolean;
  menuItems?: MenuItem[];
};

export const ItemActionDropdown = ({
  item,
  itemId,
  isOpen,
  setIsOpen,
  trigger,
  onModalOpenChange,
  minimal = false,
  menuItems,
}: ItemActionDropdownProps) => {
  const { getMenuItems, modals } = useItemActionMenuItems({
    onModalOpenChange,
  });
  const effectiveMenuItems = menuItems ?? getMenuItems(item, { minimal, itemId });

  return (
    <>
      <DropdownMenu
        options={effectiveMenuItems}
        isOpen={isOpen}
        onOpenChange={setIsOpen}
      >
        {trigger}
      </DropdownMenu>
      {modals}
    </>
  );
};
