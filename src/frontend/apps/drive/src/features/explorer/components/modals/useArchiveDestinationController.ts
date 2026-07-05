import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useModal } from "@gouvfr-lasuite/cunningham-react";
import { useItem } from "@/features/explorer/hooks/useQueries";

type UseArchiveDestinationControllerParams = {
  isOpen: boolean;
  initialDestinationFolderId?: string;
};

export const useArchiveDestinationController = ({
  isOpen,
  initialDestinationFolderId,
}: UseArchiveDestinationControllerParams) => {
  const { t } = useTranslation();
  const pickFolderModal = useModal();
  const [destinationFolderId, setDestinationFolderId] = useState<
    string | undefined
  >(initialDestinationFolderId);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setDestinationFolderId(initialDestinationFolderId);
  }, [initialDestinationFolderId, isOpen]);

  const effectiveDestinationId = destinationFolderId;
  const destinationItem = useItem(effectiveDestinationId || "", {
    enabled: !!effectiveDestinationId,
  });

  const destinationLabel = useMemo(() => {
    if (!effectiveDestinationId) {
      return t("explorer.actions.archive.common.destination_unknown");
    }
    return (
      destinationItem.data?.title ||
      t("explorer.actions.archive.common.destination_loading")
    );
  }, [destinationItem.data?.title, effectiveDestinationId, t]);

  return {
    destinationFolderId,
    destinationItem,
    destinationLabel,
    effectiveDestinationId,
    pickFolderModal,
    pickFolderModalProps: {
      ...pickFolderModal,
      initialFolderId: effectiveDestinationId,
      onPick: (folderId: string) => setDestinationFolderId(folderId),
    },
    setDestinationFolderId,
  };
};
