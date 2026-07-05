export const openSingleItemModal = <TItem,>({
  item,
  openModal,
  setCurrentItem,
}: {
  item: TItem;
  openModal: () => void;
  setCurrentItem: (item: TItem) => void;
}) => {
  setCurrentItem(item);
  openModal();
};
