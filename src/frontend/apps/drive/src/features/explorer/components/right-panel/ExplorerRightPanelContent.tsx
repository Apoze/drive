import React from "react";
import { Item, ItemUploadState } from "@/features/drivers/types";
import { ItemIcon } from "../icons/ItemIcon";
import { Button, useModal } from "@gouvfr-lasuite/cunningham-react";
import { useGlobalExplorer } from "../GlobalExplorerContext";
import { InfoRow } from "@/features/ui/components/info/InfoRow";
import { useTranslation } from "react-i18next";

import multipleSelection from "@/assets/mutliple-selection.png";
import emptySelection from "@/assets/empty-selection.png";
import { IconSize } from "@gouvfr-lasuite/ui-kit";
import { ItemInfo } from "@/features/items/components/ItemInfo";
import { MountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";
import { createAndCopyMountShareLink } from "@/features/mounts/utils/mountShareLink";
import { ItemShareModalLauncher } from "../itemShareModalLauncher";

type ExplorerRightPanelContentProps = {
  item?: Item;
};

export const ExplorerRightPanelContent = ({
  item,
}: ExplorerRightPanelContentProps) => {
  const { closeRightPanel, selectedItems } = useGlobalExplorer();
  const shareModal = useModal();
  const { t } = useTranslation();

  const firstSelectedItem = item ?? selectedItems[0];

  const showWarning =
    firstSelectedItem?.upload_state === ItemUploadState.SUSPICIOUS ||
    firstSelectedItem?.upload_state ===
      ItemUploadState.FILE_TOO_LARGE_TO_ANALYZE ||
    firstSelectedItem?.upload_state === ItemUploadState.EXPIRED;
  const canOpenStandardShare = Boolean(firstSelectedItem?.abilities.accesses_view);
  const mountShareItem =
    firstSelectedItem && "mountMeta" in firstSelectedItem
      ? (firstSelectedItem as MountExplorerItem)
      : undefined;
  const canCreateMountShareLink = Boolean(
    mountShareItem?.mountMeta.abilities?.share_link_create,
  );

  if (!firstSelectedItem) {
    return (
      <div className="explorer__right-panel__empty-selection">
        <div className="explorer__right-panel__multiple-selection__close">
          <Button
            size="small"
            variant="tertiary"
            icon={<span className="material-icons">close</span>}
            onClick={closeRightPanel}
          />
        </div>
        <img
          src={emptySelection.src}
          alt={t("explorer.rightPanel.empty.alt")}
        />
        <div className="explorer__right-panel__empty-selection__text">
          {t("explorer.rightPanel.empty.text")}
        </div>
      </div>
    );
  }

  if (selectedItems.length > 1) {
    return (
      <div className="explorer__right-panel__multiple-selection">
        <div className="explorer__right-panel__multiple-selection__close">
          <Button
            size="small"
            variant="tertiary"
            icon={<span className="material-icons">close</span>}
            onClick={closeRightPanel}
          />
        </div>
        <img src={multipleSelection.src} alt={selectedItems[0].title} />
        <div className="explorer__right-panel__multiple-selection__text">
          {t("explorer.rightPanel.multipleSelection.text")}
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="explorer__right-panel" data-testid="right-panel">
        <div className="explorer__right-panel__section p">
          <div className="explorer__right-panel__item-title">
            <div className="explorer__right-panel__item-title__close">
              <Button
                size="small"
                variant="tertiary"
                icon={<span className="material-icons">close</span>}
                onClick={closeRightPanel}
              />
            </div>
            <div className="explorer__right-panel__item-title__icon">
              <ItemIcon
                item={firstSelectedItem}
                size={IconSize.SMALL}
                type="mini"
              />
            </div>
            <div className="explorer__right-panel__item-title__text">
              {firstSelectedItem.title}
            </div>
          </div>
          <div className="explorer__right-panel__item-type">
            <ItemIcon item={firstSelectedItem} size={IconSize.X_LARGE} />
          </div>
          {showWarning && (
            <div className="explorer__right-panel__suspicious-warning">
              <div className="explorer__right-panel__suspicious-warning__text">
                {t(
                  `explorer.rightPanel.${firstSelectedItem.upload_state}.text`
                )}
              </div>
            </div>
          )}
          {(canOpenStandardShare || canCreateMountShareLink) && (
            <InfoRow
              label={t("explorer.rightPanel.sharing")}
              rightContent={
                canOpenStandardShare ? (
                  firstSelectedItem?.nb_accesses &&
                  firstSelectedItem?.nb_accesses > 1 ? (
                    <Button
                      variant="secondary"
                      icon={<span className="material-icons">group</span>}
                      onClick={shareModal.open}
                    >
                      {firstSelectedItem?.nb_accesses}
                    </Button>
                  ) : (
                    <Button variant="tertiary" onClick={shareModal.open}>
                      {t("explorer.rightPanel.share")}
                    </Button>
                  )
                ) : (
                  <Button
                    variant="tertiary"
                    onClick={() => {
                      if (!mountShareItem) {
                        return;
                      }
                      void createAndCopyMountShareLink(mountShareItem);
                    }}
                  >
                    {t("explorer.rightPanel.share")}
                  </Button>
                )
              }
            />
          )}
        </div>

        <ItemInfo item={firstSelectedItem} />
      </div>
      <ItemShareModalLauncher
        isOpen={shareModal.isOpen}
        item={canOpenStandardShare ? firstSelectedItem : undefined}
        onClose={shareModal.close}
      />
    </>
  );
};
