export const shouldFetchNextPage = ({
  entry,
  hasNextPage,
  isFetchingNextPage,
}: {
  entry?: Pick<IntersectionObserverEntry, "isIntersecting">;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
}) => {
  return Boolean(entry?.isIntersecting && hasNextPage && !isFetchingNextPage);
};
