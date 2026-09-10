import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/router";
import { useTranslation } from "react-i18next";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { AppExplorer } from "@/features/explorer/components/app-view/AppExplorer";
import { discoveryToMountExplorerItem } from "@/features/mounts/utils/mountExplorerItems";
import { DefaultRoute } from "@/utils/defaultRoutes";
import { StoragePage, StorageSpace, resourceHref, storageRequest } from "./api";
import { useStorageAdministration } from "./api";
import Link from "next/link";

const folder = (id: string, title: string, updatedAt: string) => ({
  ...discoveryToMountExplorerItem({
    mount_id: id,
    display_name: title,
    provider: "virtual",
    capabilities: {},
  }),
  id,
  title,
  updated_at: new Date(updatedAt),
});

export const SpacesExplorer = ({ spaceId }: { spaceId?: string }) => {
  const { t } = useTranslation();
  const router = useRouter();
  const administration = useStorageAdministration();
  const catalogue = useInfiniteQuery({
    queryKey: ["storage", "spaces"],
    enabled: !spaceId,
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      storageRequest<StoragePage<StorageSpace>>("spaces/", {
        params: { offset: pageParam, limit: 50 },
      }),
    getNextPageParam: (page, pages) =>
      page.next ? pages.length * 50 : undefined,
    refetchInterval: (query) =>
      query.state.data?.pages.some((page) =>
        page.results.some((space) => space.state === "index_pending"),
      )
        ? 10000
        : false,
  });
  const current = useQuery({
    queryKey: ["storage", "space", spaceId],
    enabled: Boolean(spaceId),
    queryFn: () => storageRequest<StorageSpace>(`spaces/${spaceId}/`),
  });
  const spaces = catalogue.data?.pages.flatMap((page) => page.results) ?? [];
  const entries = spaceId
    ? current.data?.roots.map((root) =>
        folder(root.id, root.title, root.updated_at),
      )
    : spaces.map((space) => folder(space.id, space.name, space.updated_at));
  const error = spaceId ? current.isError : catalogue.isError;
  return (
    <AppExplorer
      viewConfigKey={DefaultRoute.MY_FILES}
      childrenItems={entries}
      isLoading={spaceId ? current.isPending : catalogue.isPending}
      showFilters={false}
      disableDefaultContextMenu
      gridActionsCell={() => null}
      disableItemDragAndDrop
      canSelect={() => false}
      hasNextPage={!spaceId && catalogue.hasNextPage}
      fetchNextPage={() => {
        void catalogue.fetchNextPage();
      }}
      gridHeader={
        <div>
          <h1>{current.data?.name ?? t("storage.spaces")}</h1>
          <p>
            <Link href="/explorer/transfers">
              {t("storage.transfers.title")}
            </Link>
          </p>
          {administration.data?.spaces_manage && (
            <Link href="/explorer/administration/storage">
              {t("storage.administration")}
            </Link>
          )}
          {error && (
            <p role="alert">
              {t("storage.load_error")}{" "}
              <Button
                variant="tertiary"
                onClick={() => {
                  void (spaceId ? current.refetch() : catalogue.refetch());
                }}
              >
                {t("common.retry")}
              </Button>
            </p>
          )}
          {!error && entries?.length === 0 && (
            <p role="status">{t("storage.no_spaces")}</p>
          )}
        </div>
      }
      onNavigate={({ item }) => {
        if (spaceId) {
          void router.push(resourceHref(item.id, spaceId));
          return;
        }
        const space = spaces.find((value) => value.id === item.id);
        if (space?.roots.length === 1)
          void router.push(resourceHref(space.roots[0].id, space.id));
        else if (space) void router.push(`/explorer/spaces/${space.id}`);
      }}
    />
  );
};
