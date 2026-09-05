import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

import type { ItemActivity } from "@/features/drivers/types";
import { useItemActivity } from "@/features/explorer/hooks/useQueries";

type ItemActivitySectionProps = {
  itemId: string;
};

const localizePayload = (activity: ItemActivity, t: TFunction) => {
  const payload = { ...activity.payload };
  ["role", "old_role", "new_role"].forEach((key) => {
    if (payload[key]) {
      payload[key] = t(`roles.${payload[key]}`);
    }
  });
  ["reach", "old_reach", "new_reach"].forEach((key) => {
    if (payload[key]) {
      payload[key] = t(`explorer.rightPanel.activity.reaches.${payload[key]}`);
    }
  });
  payload.old_parent_name ??= t("explorer.rightPanel.activity.root");
  payload.new_parent_name ??= t("explorer.rightPanel.activity.root");
  return payload;
};

const formatRelativeDate = (value: string, language: string) => {
  const seconds = (new Date(value).getTime() - Date.now()) / 1000;
  const absolute = Math.abs(seconds);
  const [divisor, unit]: [number, Intl.RelativeTimeFormatUnit] =
    absolute < 60
      ? [1, "second"]
      : absolute < 3600
        ? [60, "minute"]
        : absolute < 86400
          ? [3600, "hour"]
          : absolute < 2592000
            ? [86400, "day"]
            : absolute < 31536000
              ? [2592000, "month"]
              : [31536000, "year"];
  return new Intl.RelativeTimeFormat(language, { numeric: "auto" }).format(
    Math.round(seconds / divisor),
    unit,
  );
};

export const ItemActivitySection = ({ itemId }: ItemActivitySectionProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const { t, i18n } = useTranslation();
  const activityQuery = useItemActivity(itemId, isOpen);
  const activities =
    activityQuery.data?.pages.flatMap((page) => page.results) ?? [];

  return (
    <section className="explorer__right-panel__activity">
      <button
        type="button"
        className="explorer__right-panel__activity__toggle"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((open) => !open)}
      >
        <span>{t("explorer.rightPanel.activity.title")}</span>
        <span className="material-icons" aria-hidden="true">
          {isOpen ? "expand_less" : "expand_more"}
        </span>
      </button>

      {isOpen && (
        <div className="explorer__right-panel__activity__content">
          {activityQuery.isLoading && (
            <p>{t("explorer.rightPanel.activity.loading")}</p>
          )}
          {activityQuery.isError && (
            <div>
              <p>{t("explorer.rightPanel.activity.error")}</p>
              <button
                type="button"
                onClick={() => void activityQuery.refetch()}
              >
                {t("explorer.rightPanel.activity.retry")}
              </button>
            </div>
          )}
          {!activityQuery.isLoading &&
            !activityQuery.isError &&
            !activities.length && (
              <p>{t("explorer.rightPanel.activity.empty")}</p>
            )}
          {!!activities.length && (
            <ul className="explorer__right-panel__activity__list">
              {activities.map((activity) => {
                const exactDate = new Intl.DateTimeFormat(i18n.language, {
                  dateStyle: "long",
                  timeStyle: "short",
                }).format(new Date(activity.created_at));
                const actor =
                  activity.actor === null &&
                  activity.actor_name === "Visitor via link"
                    ? t("explorer.rightPanel.activity.public_link_actor")
                    : activity.actor_name;
                return (
                  <li key={activity.id}>
                    <div>
                      {t(
                        `explorer.rightPanel.activity.actions.${activity.action}`,
                        {
                          actor,
                          ...localizePayload(activity, t),
                        },
                      )}
                    </div>
                    <time
                      dateTime={activity.created_at}
                      title={exactDate}
                      aria-label={exactDate}
                    >
                      {formatRelativeDate(activity.created_at, i18n.language)}
                    </time>
                  </li>
                );
              })}
            </ul>
          )}
          {activityQuery.hasNextPage && (
            <button
              type="button"
              disabled={activityQuery.isFetchingNextPage}
              onClick={() => void activityQuery.fetchNextPage()}
            >
              {t("explorer.rightPanel.activity.load_more")}
            </button>
          )}
        </div>
      )}
    </section>
  );
};
