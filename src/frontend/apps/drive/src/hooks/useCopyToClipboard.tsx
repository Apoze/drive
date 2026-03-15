import {
  addToast,
  ToasterItem,
} from "@/features/ui/components/toaster/Toaster";
import { useCallback } from "react";
import { useTranslation } from "react-i18next";

const fallbackWriteText = (text: string) => {
  if (typeof document === "undefined") {
    throw new Error("Clipboard unavailable");
  }

  const textarea = document.createElement("textarea");
  const activeElement = document.activeElement instanceof HTMLElement
    ? document.activeElement
    : null;

  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.setAttribute("aria-hidden", "true");
  textarea.style.position = "fixed";
  textarea.style.top = "0";
  textarea.style.left = "-9999px";
  textarea.style.opacity = "0";

  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);

  try {
    const copied = document.execCommand?.("copy");

    if (!copied) {
      throw new Error("Clipboard unavailable");
    }
  } finally {
    document.body.removeChild(textarea);
    activeElement?.focus();
  }
};

const writeTextToClipboard = async (text: string) => {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  fallbackWriteText(text);
};

export const useClipboard = () => {
  const { t } = useTranslation();

  return useCallback(
    (text: string, successMessage?: string, errorMessage?: string) => {
      writeTextToClipboard(text)
        .then(() => {
          addToast(
            <ToasterItem>
              <span className="material-icons">check</span>
              <span>{successMessage ?? t("clipboard.success")}</span>
            </ToasterItem>
          );
        })
        .catch(() => {
          addToast(
            <ToasterItem type="error">
              <span className="material-icons">error</span>
              <span>{errorMessage ?? t("clipboard.error")}</span>
            </ToasterItem>
          );
        });
    },
    [t]
  );
};
