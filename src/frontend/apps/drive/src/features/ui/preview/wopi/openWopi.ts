export const WOPI_TAB_PATH = "/wopi";

export const openWopiInNewTab = (itemId: string) => {
  window.open(`${WOPI_TAB_PATH}/${itemId}`, "_blank", "noopener,noreferrer");
};
