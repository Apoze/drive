import { UserSearchFilter, UserSearchFilterItem } from "@gouvfr-lasuite/ui-kit";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useContacts } from "@/features/users/hooks/useUserQueries";

const contactLabel = (user?: UserSearchFilterItem) => user?.fullName || "";

export const ExplorerFilterContact = (props: {
  value?: string;
  onChange: (value?: string) => void;
}) => {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");

  // The query only runs while the popover is open so navigating folders does
  // not trigger contact requests the user never asked for. The backend handles
  // the search through the `q` param, so there is no local filtering.
  const { data: contacts, isLoading } = useContacts(
    { q: search },
    { enabled: isOpen },
  );

  const users = contacts ?? [];
  const items: UserSearchFilterItem[] = useMemo(
    () =>
      users.map((user) => ({
        id: user.id,
        label: user.full_name,
        fullName: user.full_name,
      })),
    [users],
  );

  const selectedUser = useMemo(
    () => items.find((user) => user.id === props.value),
    [items, props.value],
  );

  return (
    <UserSearchFilter
      label={t("explorer.filters.contact.label")}
      activeLabel={selectedUser ? contactLabel(selectedUser) : undefined}
      isActive={!!props.value}
      searchValue={search}
      onSearchChange={setSearch}
      items={items}
      onItemSelect={(user) => {
        props.onChange(user?.id);
      }}
      isLoading={isLoading}
      isOpen={isOpen}
      onOpenChange={setIsOpen}
    />
  );
};
