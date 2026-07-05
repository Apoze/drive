import React from "react";
import {
  Button,
  Modal,
  ModalProps,
  ModalSize,
} from "@gouvfr-lasuite/cunningham-react";
import { useTranslation } from "react-i18next";
import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { useMutationCreateNewFile } from "../../hooks/useMutations";
import { useGlobalExplorer } from "../GlobalExplorerContext";
import { useRouter } from "next/router";
import {
  buildCreateFileMutationPayload,
  canSubmitCreateFile,
  CREATE_FILE_EXTENSIONS_BY_KIND,
  CreateFileKind,
  DEFAULT_CREATE_FILE_EXTENSION_BY_KIND,
  filterCreateFileExtensionOptions,
  getCreateFileInitialState,
  shouldRedirectToMyFiles,
  splitCreateFileExtensionOptions,
} from "./itemMutationModalHelpers";

export enum ExplorerCreateFileType {
  DOC = "doc",
  POWERPOINT = "powerpoint",
  CALC = "calc",
}

type ExplorerCreateFileModalProps = Pick<ModalProps, "isOpen" | "onClose"> & {
  parentId?: string;
  canCreateChildren?: boolean;
  /**
   * When set, opens the modal in a constrained "quick-create" mode (ODF only).
   * When unset, the modal stays in the existing advanced mode ("More formats…").
   */
  type?: ExplorerCreateFileType;
};

const QUICK_PRESET_BY_TYPE: Record<
  ExplorerCreateFileType,
  { kind: CreateFileKind; extension: string }
> = {
  [ExplorerCreateFileType.DOC]: { kind: "text", extension: "odt" },
  [ExplorerCreateFileType.CALC]: { kind: "sheet", extension: "ods" },
  [ExplorerCreateFileType.POWERPOINT]: { kind: "slide", extension: "odp" },
};

export const ExplorerCreateFileModal = ({
  canCreateChildren = true,
  ...props
}: ExplorerCreateFileModalProps) => {
  const { t } = useTranslation();
  const router = useRouter();
  const createNewFile = useMutationCreateNewFile();
  const { openSinglePreview } = useGlobalExplorer();

  const quickPreset = props.type ? QUICK_PRESET_BY_TYPE[props.type] : undefined;
  const isQuickCreate = Boolean(quickPreset);

  const initialState = getCreateFileInitialState();
  const [kind, setKind] = useState<CreateFileKind>(initialState.kind);
  const [extension, setExtension] = useState<string>(initialState.extension);
  const [filenameStem, setFilenameStem] = useState<string>(
    initialState.filenameStem,
  );
  const [extensionSearch, setExtensionSearch] = useState<string>(
    initialState.extensionSearch,
  );

  useEffect(() => {
    if (!props.isOpen) {
      return;
    }
    const nextState = getCreateFileInitialState(quickPreset);
    setKind(nextState.kind);
    setExtension(nextState.extension);
    setFilenameStem(nextState.filenameStem);
    setExtensionSearch(nextState.extensionSearch);
  }, [props.isOpen, quickPreset]);

  const options = useMemo(() => CREATE_FILE_EXTENSIONS_BY_KIND[kind], [kind]);
  const filteredOptions = useMemo(() => {
    return filterCreateFileExtensionOptions({
      options,
      extensionSearch,
      getLabel: (option) =>
        t(`explorer.actions.createFile.extensions.${option.labelKey}`),
    });
  }, [extensionSearch, options, t]);

  const { recommended, others } = splitCreateFileExtensionOptions(
    filteredOptions,
  );

  const canSubmit = canSubmitCreateFile({
    filenameStem,
    isPending: createNewFile.isPending,
  });

  const handleSubmit = () => {
    if (!canSubmit) {
      return;
    }

    createNewFile.mutate(
      buildCreateFileMutationPayload({
        parentId: props.parentId,
        canCreateChildren,
        filenameStem,
        extension,
        kind,
      }),
      {
        onSuccess: (created) => {
          openSinglePreview(created);
          props.onClose();
          if (shouldRedirectToMyFiles(props.parentId) || !canCreateChildren) {
            router.push(`/explorer/items/my-files`);
          }
        },
      },
    );
  };

  return (
    <Modal
      {...props}
      size={ModalSize.MEDIUM}
      title={
        isQuickCreate && props.type
          ? t(`explorer.actions.createFile.modal.title_${props.type}`)
          : t("explorer.actions.createFile.modal.title")
      }
      rightActions={
        <>
          <Button variant="bordered" onClick={props.onClose}>
            {t("common.cancel")}
          </Button>
          <Button onClick={handleSubmit} disabled={!canSubmit}>
            {t("explorer.actions.createFile.modal.submit")}
          </Button>
        </>
      }
    >
      <div className="explorer__create-file__modal">
        <div className="explorer__create-file__modal__field">
          <div className="explorer__create-file__modal__label">
            {t("explorer.actions.createFile.modal.filename_label")}
          </div>
          <div className="explorer__create-file__modal__filename-row">
            <input
              className="explorer__create-file__modal__filename-input"
              value={filenameStem}
              autoFocus={true}
              onChange={(e) => setFilenameStem(e.target.value)}
            />
            <div className="explorer__create-file__modal__extension-suffix">
              .{extension}
            </div>
          </div>
        </div>

        {!isQuickCreate && (
          <div className="explorer__create-file__modal__columns">
            <div className="explorer__create-file__modal__column">
              <div className="explorer__create-file__modal__label">
                {t("explorer.actions.createFile.modal.kind_label")}
              </div>
              <div className="explorer__create-file__modal__list">
                {(["text", "sheet", "slide"] as const).map((k) => (
                  <button
                    key={k}
                    type="button"
                    className={clsx("explorer__create-file__modal__row", {
                      selected: kind === k,
                    })}
                    onClick={() => {
                      setKind(k);
                      setExtension(DEFAULT_CREATE_FILE_EXTENSION_BY_KIND[k]);
                      setExtensionSearch("");
                    }}
                  >
                    {t(`explorer.actions.createFile.kinds.${k}`)}
                  </button>
                ))}
              </div>
            </div>

            <div className="explorer__create-file__modal__column">
              <div className="explorer__create-file__modal__label">
                {t("explorer.actions.createFile.modal.extension_label")}
              </div>

              <div className="explorer__create-file__modal__search">
                <span className="material-icons">search</span>
                <input
                  value={extensionSearch}
                  onChange={(e) => setExtensionSearch(e.target.value)}
                  placeholder={t(
                    "explorer.actions.createFile.modal.search_placeholder",
                  )}
                />
              </div>

              <div className="explorer__create-file__modal__list explorer__create-file__modal__list--scroll">
                {recommended.length > 0 && (
                  <>
                    <div className="explorer__create-file__modal__section-title">
                      {t("explorer.actions.createFile.modal.recommended")}
                    </div>
                    {recommended.map((opt) => (
                      <button
                        key={opt.ext}
                        type="button"
                        className={clsx("explorer__create-file__modal__row", {
                          selected: extension === opt.ext,
                        })}
                        onClick={() => setExtension(opt.ext)}
                      >
                        <span className="explorer__create-file__modal__ext">
                          .{opt.ext}
                        </span>
                        <span className="explorer__create-file__modal__ext-label">
                          {t(
                            `explorer.actions.createFile.extensions.${opt.labelKey}`,
                          )}
                        </span>
                      </button>
                    ))}
                  </>
                )}

                {others.length > 0 && (
                  <>
                    <div className="explorer__create-file__modal__section-title">
                      {t("explorer.actions.createFile.modal.others")}
                    </div>
                    {others.map((opt) => (
                      <button
                        key={opt.ext}
                        type="button"
                        className={clsx("explorer__create-file__modal__row", {
                          selected: extension === opt.ext,
                        })}
                        onClick={() => setExtension(opt.ext)}
                      >
                        <span className="explorer__create-file__modal__ext">
                          .{opt.ext}
                        </span>
                        <span className="explorer__create-file__modal__ext-label">
                          {t(
                            `explorer.actions.createFile.extensions.${opt.labelKey}`,
                          )}
                        </span>
                      </button>
                    ))}
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
};
