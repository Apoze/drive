export const docsCreationUrl = (
  base: string | undefined,
  destination: string | undefined,
  space?: string,
): string | undefined => {
  if (!base || !destination) return undefined;
  try {
    const url = new URL(base);
    if (
      !["http:", "https:"].includes(url.protocol) ||
      url.username ||
      url.password
    )
      return undefined;
    url.pathname = `${url.pathname.replace(/\/$/, "")}/docs/new/`;
    url.search = "";
    url.hash = "";
    url.searchParams.set("drive_destination", destination);
    if (space) url.searchParams.set("drive_space_id", space);
    return url.toString();
  } catch {
    return undefined;
  }
};
