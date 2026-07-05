import React from "react";
import { useTranslation } from "react-i18next";
import { getDriver } from "../config/Config";
import { useEffect, useRef, useState } from "react";
import { Item } from "../drivers/types";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { Spinner } from "@gouvfr-lasuite/ui-kit";
import { ClientMessageType, SDKRelayManager } from "./SdkRelayManager";
import { getSdkChooseUpdates } from "./sdkRuntime";

export const PickerFooter = ({
  token,
  selectedItems,
}: {
  token: string;
  selectedItems: Item[];
}) => {
  const { t } = useTranslation();

  const driver = getDriver();

  const [waitForClosing, setWaitForClosing] = useState(false);
  const hasSentItemsSelected = useRef(false);

  const onChoose = async () => {
    await Promise.all(
      getSdkChooseUpdates(selectedItems).map((payload) => driver.updateItem(payload)),
    );

    await SDKRelayManager.registerEvent(token, {
      type: ClientMessageType.ITEMS_SELECTED,
      data: {
        items: selectedItems,
      },
    });
    hasSentItemsSelected.current = true;
    setWaitForClosing(true);
    window.close();
  };

  const onCancel = async () => {
    await SDKRelayManager.registerEvent(token, {
      type: ClientMessageType.CANCEL,
      data: {},
    });
    setWaitForClosing(true);
    window.close();
  };

  useEffect(() => {
    window.addEventListener("beforeunload", async function () {
      // We don't want to send a cancel event if the user has already selected items.
      if (hasSentItemsSelected.current) {
        return;
      }
      await SDKRelayManager.registerEvent(token, {
        type: ClientMessageType.CANCEL,
        data: {},
      });
    });
  }, []);

  return (
    <div className="sdk__explorer__footer">
      <div className="sdk__explorer__footer__caption">
        {t("sdk.explorer.picker_label", {
          count: selectedItems.length,
        })}
      </div>
      <div className="sdk__explorer__footer__actions">
        <Button
          variant="tertiary"
          onClick={onCancel}
          disabled={waitForClosing}
          icon={waitForClosing ? <Spinner size="sm" /> : undefined}
        >
          {t("sdk.explorer.cancel")}
        </Button>
        <Button
          onClick={onChoose}
          disabled={waitForClosing || selectedItems.length === 0}
          icon={waitForClosing ? <Spinner size="sm" /> : undefined}
        >
          {t("sdk.explorer.choose")}
        </Button>
      </div>
    </div>
  );
};
