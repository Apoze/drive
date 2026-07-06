import { useEffect } from "react";
import { useRouter } from "next/router";
import { useTranslation } from "react-i18next";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { Icon } from "@gouvfr-lasuite/ui-kit";

import { useItem } from "@/features/explorer/hooks/useQueries";
import { useRefreshItemCache } from "@/features/explorer/hooks/useRefreshItems";
import { itemToPreviewFile } from "@/features/explorer/utils/utils";
import { GenericDisclaimer } from "@/features/ui/components/generic-disclaimer/GenericDisclaimer";
import { SpinnerPage } from "@/features/ui/components/spinner/SpinnerPage";
import { WopiEditor } from "@/features/ui/preview/wopi/WopiEditor";
import type { FilePreviewType } from "@/features/ui/preview/files-preview/previewSource";

export default function WopiPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const itemId = typeof router.query.id === "string" ? router.query.id : "";

  const { data: item, isLoading, error } = useItem(itemId, {
    enabled: Boolean(itemId),
  });
  const refreshItemCache = useRefreshItemCache();

  useEffect(() => {
    if (!item) {
      return;
    }

    const previousTitle = document.title;
    document.title = `${item.title} - ${t("app_title")}`;

    return () => {
      document.title = previousTitle;
    };
  }, [item, t]);

  if (!itemId || isLoading || (error && [401, 403].includes(error.code))) {
    return <SpinnerPage />;
  }

  if (!item) {
    return (
      <GenericDisclaimer
        message={t("explorer.files.not_found.description")}
        imageSrc="/assets/403-background.png"
      >
        <Button href="/" icon={<Icon name="home" />}>
          {t("403.button")}
        </Button>
      </GenericDisclaimer>
    );
  }

  const handleRename = (file: FilePreviewType, newName: string) => {
    refreshItemCache(file.id, { title: newName });
  };

  return (
    <div className="wopi-page">
      <WopiEditor item={itemToPreviewFile(item)} onFileRename={handleRename} />
    </div>
  );
}
