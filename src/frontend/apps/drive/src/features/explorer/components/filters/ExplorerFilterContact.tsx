import { SearchFilter, SearchUserItem } from "@gouvfr-lasuite/ui-kit";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { UserLight } from "@/features/drivers/types";
import { useContacts, useUsers } from "@/features/users/hooks/useUserQueries";

const CONTACT_RESET = "__contact_reset__";
const CONTACT_SEARCH_MIN_LENGTH = 5;

const contactLabel = (user: UserLight) => user.full_name || user.short_name || "";

type ContactItem = { id: string; label: string; user?: UserLight };

export const ExplorerFilterContact = (props: {
  value: string | null;
  onChange: (value: string | null) => void;
}) => {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");

  const isSearching = search.length >= CONTACT_SEARCH_MIN_LENGTH;
  const { data: contacts, isLoading: isLoadingContacts } = useContacts(
    undefined,
    { enabled: !isSearching },
  );
  const { data: results, isLoading: isLoadingResults } = useUsers(
    { q: search },
    { enabled: isSearching },
  );

  const users = useMemo(() => {
    if (isSearching) {
      return results ?? [];
    }
    const list = contacts ?? [];
    if (!search) {
      return list;
    }
    const query = search.toLowerCase();
    return list.filter((user) => contactLabel(user).toLowerCase().includes(query));
  }, [contacts, isSearching, results, search]);

  const activeContact =
    contacts?.find((user) => user.id === props.value) ??
    results?.find((user) => user.id === props.value);

  const items: ContactItem[] = useMemo(
    () => [
      { id: CONTACT_RESET, label: t("explorer.filters.contact.reset") },
      ...users.map((user) => ({
        id: user.id,
        label: contactLabel(user),
        user,
      })),
    ],
    [t, users],
  );

  return (
    <SearchFilter<ContactItem>
      label={t("explorer.filters.contact.label")}
      activeLabel={activeContact ? contactLabel(activeContact) : undefined}
      isActive={!!props.value}
      placeholder={t("explorer.filters.contact.placeholder")}
      searchValue={search}
      onSearchChange={setSearch}
      items={items}
      isLoading={isSearching ? isLoadingResults : isLoadingContacts}
      emptyState={t("explorer.filters.contact.empty")}
      renderItem={(item) =>
        item.id === CONTACT_RESET ? (
          <div className="explorer__filters__item">
            <span className="material-icons">undo</span>
            {t("explorer.filters.contact.reset")}
          </div>
        ) : (
          <div className="explorer__filters__contact">
            <SearchUserItem user={{ ...item.user!, email: "" }} />
            {item.id === props.value && (
              <span className="material-icons explorer__filters__check">check</span>
            )}
          </div>
        )
      }
      onItemSelect={(item) =>
        props.onChange(item.id === CONTACT_RESET ? null : item.id)
      }
    />
  );
};
