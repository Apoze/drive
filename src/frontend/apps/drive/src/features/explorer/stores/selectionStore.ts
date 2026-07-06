import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useSyncExternalStore,
} from "react";
import { Item } from "@/features/drivers/types";

type Listener = () => void;

export type SetSelectedItemsAction =
  | Item[]
  | ((previousItems: Item[]) => Item[]);

export class SelectionStore {
  private items: Item[] = [];
  private itemsById = new Map<string, Item>();
  private readonly globalListeners = new Set<Listener>();
  private readonly idListeners = new Map<string, Set<Listener>>();

  getSelectedItems = (): Item[] => this.items;

  getSelectedItemsMap = (): Record<string, Item> =>
    Object.fromEntries(this.itemsById);

  isSelected = (id: string): boolean => this.itemsById.has(id);

  setSelectedItems = (action: SetSelectedItemsAction): void => {
    const next =
      typeof action === "function" ? action(this.items) : action;

    if (next === this.items) {
      return;
    }

    const previousMap = this.itemsById;
    const nextMap = new Map<string, Item>();
    next.forEach((item) => nextMap.set(item.id, item));

    const changedIds = new Set<string>();
    previousMap.forEach((_, id) => {
      if (!nextMap.has(id)) {
        changedIds.add(id);
      }
    });
    nextMap.forEach((item, id) => {
      if (!previousMap.has(id) || previousMap.get(id) !== item) {
        changedIds.add(id);
      }
    });

    if (changedIds.size === 0 && previousMap.size === nextMap.size) {
      return;
    }

    this.items = next;
    this.itemsById = nextMap;

    changedIds.forEach((id) => {
      this.idListeners.get(id)?.forEach((listener) => listener());
    });
    this.globalListeners.forEach((listener) => listener());
  };

  clear = (): void => {
    if (this.items.length === 0) {
      return;
    }
    this.setSelectedItems([]);
  };

  subscribe = (listener: Listener): (() => void) => {
    this.globalListeners.add(listener);
    return () => {
      this.globalListeners.delete(listener);
    };
  };

  subscribeToId = (id: string, listener: Listener): (() => void) => {
    let listeners = this.idListeners.get(id);
    if (!listeners) {
      listeners = new Set();
      this.idListeners.set(id, listeners);
    }
    listeners.add(listener);

    return () => {
      const currentListeners = this.idListeners.get(id);
      currentListeners?.delete(listener);
      if (currentListeners?.size === 0) {
        this.idListeners.delete(id);
      }
    };
  };
}

export const SelectionStoreContext = createContext<SelectionStore | undefined>(
  undefined,
);

export const useSelectionStore = (): SelectionStore => {
  const store = useContext(SelectionStoreContext);
  if (!store) {
    throw new Error(
      "useSelectionStore must be used within a SelectionStoreContext.Provider",
    );
  }
  return store;
};

export const useSelectedItems = (): Item[] => {
  const store = useSelectionStore();
  return useSyncExternalStore(
    store.subscribe,
    store.getSelectedItems,
    store.getSelectedItems,
  );
};

export const useHasSelection = (): boolean => {
  const store = useSelectionStore();
  return useSyncExternalStore(
    store.subscribe,
    () => store.getSelectedItems().length > 0,
    () => store.getSelectedItems().length > 0,
  );
};

export const useSelectionCount = (): number => {
  const store = useSelectionStore();
  return useSyncExternalStore(
    store.subscribe,
    () => store.getSelectedItems().length,
    () => store.getSelectedItems().length,
  );
};

export const useIsItemSelected = (id: string): boolean => {
  const store = useSelectionStore();
  const subscribe = useCallback(
    (listener: Listener) => store.subscribeToId(id, listener),
    [id, store],
  );
  const getSnapshot = useCallback(() => store.isSelected(id), [id, store]);
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
};

export const useSetSelectedItems = (): SelectionStore["setSelectedItems"] => {
  return useSelectionStore().setSelectedItems;
};

export const useCreateSelectionStore = (): SelectionStore => {
  const ref = useRef<SelectionStore | null>(null);
  if (ref.current === null) {
    ref.current = new SelectionStore();
  }
  return ref.current;
};
