import React from "react";
import { Button, Modal, ModalProps, ModalSize } from "@gouvfr-lasuite/cunningham-react";
import { useTranslation } from "react-i18next";

import {
  QuickSearch,
  QuickSearchGroup,
  QuickSearchItemTemplate,
} from "@gouvfr-lasuite/ui-kit";
import { Item } from "@/features/drivers/types";
import { ItemIcon } from "../../icons/ItemIcon";
import {
  ExplorerFilterType,
  ExplorerFilterWorkspace,
  ExplorerFilterScope,
} from "../../app-view/ExplorerFilters";
import { ItemFilters } from "@/features/drivers/Driver";
import { getItemTitle } from "@/features/explorer/utils/utils";
import { useExplorerSearchController } from "./useExplorerSearchController";

type ExplorerSearchModalProps = Pick<ModalProps, "isOpen" | "onClose"> & {
  defaultFilters?: ItemFilters;
};

export const ExplorerSearchModal = (props: ExplorerSearchModalProps) => {
  const { t } = useTranslation();
  const {
    inputValue,
    loading,
    items,
    filters,
    isMinimalLayout,
    showResetFilters,
    onInputChange,
    onFilterChange,
    onResetFilters,
    onItemClick,
    bindContainerRef,
  } = useExplorerSearchController(props);

  return (
    <Modal
      {...props}
      closeOnClickOutside
      size={ModalSize.MEDIUM}
      title={t("explorer.search.modal.title")}
    >
      <div className="explorer__search__modal" ref={bindContainerRef}>
        <QuickSearch
          onFilter={onInputChange}
          inputValue={inputValue}
          loading={loading}
          placeholder={t("explorer.search.modal.placeholder")}
        >
          <div className="explorer__search__modal__filters">
            <div className="explorer__search__modal__filters__inputs">
              <ExplorerFilterType
                value={filters?.type ?? null}
                onChange={(value) => onFilterChange("type", value)}
              />
              <ExplorerFilterWorkspace
                value={filters?.workspace ?? null}
                isDisabled={isMinimalLayout}
                onChange={(value) => onFilterChange("workspace", value)}
              />
              <ExplorerFilterScope
                value={filters?.scope ?? null}
                onChange={(value) => onFilterChange("scope", value)}
              />
            </div>

            <div>
              {showResetFilters && (
                <Button
                  variant="tertiary"
                  size="small"
                  onClick={onResetFilters}
                >
                  {t("explorer.search.modal.filters.reset")}
                </Button>
              )}
            </div>
          </div>
          {items.length > 0 && (
            <div className="explorer__search__modal__items__container">
              <div className="explorer__search__modal__items">
                <QuickSearchGroup
                  onSelect={onItemClick}
                  renderElement={(element) => <SearchItem item={element} />}
                  group={{
                    groupName: t("explorer.search.modal.results"),
                    elements: items,
                  }}
                />
              </div>
            </div>
          )}
        </QuickSearch>
      </div>
    </Modal>
  );
};

const SearchItem = ({ item }: { item: Item }) => {
  const { t } = useTranslation();
  const shouldShowAncestors =
    (item.parents && item.parents.length > 0) || item.deleted_at;
  return (
    <QuickSearchItemTemplate
      right={
        <span className="material-icons explorer__search__modal__item__right-icon">
          keyboard_return
        </span>
      }
      left={
        <div
          className="explorer__search__modal__item"
          data-testid="search-item"
        >
          <div className="explorer__search__modal__item__icon">
            <ItemIcon item={item} />
          </div>
          <div className="explorer__search__modal__item__content">
            <div className="explorer__search__modal__item__content__title">
              {getItemTitle(item)}
            </div>
            {shouldShowAncestors && (
              <div className="explorer__search__modal__item__content__ancestors">
                {item.deleted_at
                  ? t("explorer.tree.trash")
                  : item.parents
                      ?.map((ancestor) => getItemTitle(ancestor))
                      .join(" / ")}
              </div>
            )}
          </div>
        </div>
      }
    />
  );
};
