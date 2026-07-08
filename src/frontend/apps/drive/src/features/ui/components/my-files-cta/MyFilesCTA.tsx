import { DefaultRoute, ORDERED_DEFAULT_ROUTES } from "@/utils/defaultRoutes";
import { Button } from "@gouvfr-lasuite/cunningham-react";
import { Icon } from "@gouvfr-lasuite/ui-kit";
import { useTranslation } from "react-i18next";

export const MyFilesCTA = () => {
  const { t } = useTranslation();
  const myFilesRoute = ORDERED_DEFAULT_ROUTES.find(
    (route) => route.id === DefaultRoute.MY_FILES,
  );

  return (
    <Button
      variant="secondary"
      size="small"
      href={myFilesRoute?.route ?? "/explorer/items/my-files"}
      icon={<Icon name="folder" />}
      data-testid="my-files-cta"
    >
      {t("my_files_cta.my_files")}
    </Button>
  );
};
