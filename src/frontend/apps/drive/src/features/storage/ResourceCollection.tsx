import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Button,
  Input,
  Modal,
  ModalProps,
  ModalSize,
} from "@gouvfr-lasuite/cunningham-react";
import { AppExplorer } from "@/features/explorer/components/app-view/AppExplorer";
import { DefaultRoute } from "@/utils/defaultRoutes";
import { ItemFilters } from "@/features/drivers/Driver";
import { useItemActionMenuItems } from "@/features/explorer/hooks/useItemActionMenuItems";
import { useGlobalExplorer } from "@/features/explorer/components/GlobalExplorerContext";
import { ItemsBrowsePreviewHost } from "@/features/explorer/components/items-browse/ItemsBrowseExplorer";
import { convertFiltersToQueryParams } from "@/features/explorer/components/filters/filterUtils";
import { ItemType } from "@/features/drivers/types";
import { openFileFromExplorer } from "@/features/explorer/utils/fileOpenAction";
import {
  StorageResource,
  StoragePage,
  resourceHref,
  resourceItem,
  storageRequest,
} from "./api";

export const ResourceCollection = ({
  mode,
  query = "",
  onNavigate,
}: {
  mode: "search" | "favorites" | "recent" | "home";
  query?: string;
  onNavigate?: () => void;
}) => {
  const { t } = useTranslation();
  const router = useRouter();
  const cache = useQueryClient();
  const [actionFailed, setActionFailed] = useState(false);
  const [filters, setFilters] = useState<ItemFilters>({});
  const { getMenuItems, modals } = useItemActionMenuItems();
  const { openPreview } = useGlobalExplorer();
  const rows = useInfiniteQuery({
    queryKey: ["storage", "resources", mode, query, filters],
    enabled: mode !== "search" || query.length >= 2,
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      storageRequest<StoragePage<StorageResource>>("resources/", {
        params: {
          ...(mode === "home"
            ? Object.fromEntries(
                Object.entries(convertFiltersToQueryParams(filters)).filter(
                  ([, value]) => value !== undefined,
                ),
              )
            : {}),
          mode,
          q: query,
          offset: pageParam,
          limit: 50,
        },
      }),
    getNextPageParam: (page, pages) =>
      page.next ? pages.length * 50 : undefined,
  });
  const resources = rows.data?.pages.flatMap((page) => page.results) ?? [];
  const mapped = resources.map((resource) => ({
    resource,
    item: resourceItem(resource),
  }));
  const open = (id: string) => {
    const row = mapped.find((row) => row.item.id === id);
    if (row?.item.type === ItemType.DOCS) {
      openFileFromExplorer({
        item: row.item,
        openPreview: () => undefined,
        onPreviewUnavailable: () => setActionFailed(true),
      });
      return;
    }
    const target = row?.resource;
    if (
      mode === "home" &&
      row?.item.type === ItemType.FILE &&
      target?.adapter.kind === "item"
    ) {
      openFileFromExplorer({
        item: row.item,
        openPreview: (item) =>
          openPreview(
            item,
            mapped
              .filter(({ resource }) => resource.adapter.kind === "item")
              .map(({ item }) => item),
          ),
        onPreviewUnavailable: () => setActionFailed(true),
      });
      return;
    }
    if (target) {
      onNavigate?.();
      void router.push(resourceHref(target.id, target.space));
    }
  };
  const favorite = (resource: StorageResource) => {
    setActionFailed(false);
    void storageRequest(
      `resources/${resource.id}/favorite/?space=${resource.space}`,
      { method: mode === "favorites" ? "DELETE" : "POST" },
    )
      .then(() =>
        cache.invalidateQueries({ queryKey: ["storage", "resources"] }),
      )
      .catch(() => setActionFailed(true));
  };
  return (
    <>
      <AppExplorer
        viewConfigKey={
          mode === "home"
            ? DefaultRoute.MY_FILES
            : mode === "favorites"
              ? DefaultRoute.FAVORITES
              : DefaultRoute.RECENT
        }
        onComputedFiltersChange={mode === "home" ? setFilters : undefined}
        childrenItems={mapped.map((row) => row.item)}
        showFilters={mode === "home"}
        disableItemDragAndDrop={mode !== "home"}
        disableDefaultContextMenu
        canSelect={(item) =>
          item.abilities.retrieve &&
          (mode !== "home" ||
            mapped.find((row) => row.item.id === item.id)?.resource.adapter
              .kind === "item")
        }
        isLoading={rows.isFetching && !rows.data}
        hasNextPage={rows.hasNextPage}
        isFetchingNextPage={rows.isFetchingNextPage}
        fetchNextPage={() => {
          void rows.fetchNextPage();
        }}
        onNavigate={({ item }) => open(item.id)}
        onFileClick={(item) => open(item.id)}
        getContextMenuItems={(item) => {
          const target = mapped.find(
            (row) => row.item.id === item.id,
          )?.resource;
          if (mode === "home" && target?.adapter.kind === "item")
            return getMenuItems(item);
          return target
            ? [
                { label: t("storage.open"), callback: () => open(item.id) },
                {
                  label: t(
                    mode === "favorites"
                      ? "storage.remove_favorite"
                      : "storage.add_favorite",
                  ),
                  callback: () => favorite(target),
                },
              ]
            : [];
        }}
        gridHeader={
          mode === "home" ? undefined : (
            <>
              {(rows.isError || actionFailed) && (
                <p role="alert">
                  {t("storage.load_error")}{" "}
                  <Button
                    variant="tertiary"
                    onClick={() => {
                      void rows.refetch();
                    }}
                  >
                    {t("common.retry")}
                  </Button>
                </p>
              )}
              {!rows.isFetching && !resources.length && (
                <p role="status">
                  {t(
                    mode === "search" && query.length < 2
                      ? "storage.search_hint"
                      : "storage.no_results",
                  )}
                </p>
              )}
            </>
          )
        }
      />
      {mode === "home" && (
        <>
          {rows.isError && (
            <p role="alert">
              {t("storage.load_error")}{" "}
              <Button variant="tertiary" onClick={() => void rows.refetch()}>
                {t("common.retry")}
              </Button>
            </p>
          )}
          {actionFailed && <p role="alert">{t("storage.load_error")}</p>}
          {modals}
          <ItemsBrowsePreviewHost />
        </>
      )}
    </>
  );
};

export const ResourceSearchModal = (
  props: Pick<ModalProps, "isOpen" | "onClose">,
) => {
  const { t } = useTranslation();
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setQuery(input.trim()), 250);
    return () => clearTimeout(timer);
  }, [input]);
  return (
    <Modal
      {...props}
      size={ModalSize.LARGE}
      title={t("explorer.search.modal.title")}
      closeOnEsc
      closeOnClickOutside
    >
      <Input
        label={t("explorer.search.modal.placeholder")}
        value={input}
        autoFocus
        onChange={(event) => setInput(event.target.value)}
      />
      {props.isOpen && (
        <ResourceCollection
          mode="search"
          query={query}
          onNavigate={() => props.onClose?.()}
        />
      )}
    </Modal>
  );
};
