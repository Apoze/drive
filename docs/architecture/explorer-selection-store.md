# Explorer Selection Store

The explorer selection state uses an external store backed by
`useSyncExternalStore` instead of a React `useState` value on
`GlobalExplorerContext`.

The goal is to keep range selection responsive in large folders. A marquee
selection can change a few row ids on every mouse move; pushing those updates
through the global explorer context would re-render the whole explorer shell
and every grid row. The selection store keeps the selected item list outside
React context and lets rows subscribe only to their own selected state.

## Store Contract

`src/frontend/apps/drive/src/features/explorer/stores/selectionStore.ts`
exposes:

- `SelectionStore`, holding the selected `Item[]` plus an id map.
- `SelectionStoreContext`, carrying the nearest store instance.
- `useSelectedItems()`, for components that need the full selected list.
- `useHasSelection()` and `useSelectionCount()`, for narrow shell state.
- `useIsItemSelected(id)`, for row and cell subscriptions.
- `useSetSelectedItems()`, for selection updates.
- `useCreateSelectionStore()`, for creating a stable scoped store.

`SelectionStore.setSelectedItems()` accepts the same array-or-updater shape as
React state setters. It diffs the previous and next selected ids and notifies
only listeners whose id status changed. Components subscribed through
`useIsItemSelected(id)` therefore re-render only when that item's selected
boolean flips.

## Scopes

The app explorer gets its store from `GlobalExplorerProvider`. Embedded
explorers create their own local store through `useEmbeddedExplorer`, then
shadow the parent `SelectionStoreContext` for the embedded grid subtree.

This keeps the main explorer selection separate from move modals and SDK
pickers. In particular, SDK picker selection still goes through the embedded
explorer scope and keeps its `canPickSdkItem` rules; it must not subscribe to
or mutate the main explorer selection store.

## Compatibility

This fork keeps `selectedItems`, `selectedItemsMap`, and `setSelectedItems` on
`GlobalExplorerContext` as compatibility fields. New explorer code should use
the selection-store hooks directly. The compatibility fields are snapshots for
older fork-local consumers and should not be used in performance-sensitive row
or cell paths.

`clearSelection`, `replaceSelection`, and `selectSingleItem` are still the
canonical context APIs for callers that intentionally operate at explorer-shell
level. They now delegate to the same store instance.

## Performance Rules

- Grid rows and cells should use `useIsItemSelected(item.id)` when they only
  need a boolean selected state.
- Explorer shell components should use `useHasSelection()` or
  `useSelectionCount()` instead of the full selected list whenever possible.
- Event handlers may read the store imperatively with
  `selectionStore.getSelectedItems()` or `selectionStore.isSelected(id)` to
  avoid subscribing a parent component.
- Do not pass selected item maps through grid context; that recreates the
  context-driven render storm this store avoids.

## Mount, Trash, And Preview Boundaries

The store changes selection plumbing only. It does not change mount action
capabilities, trash restore/hard-delete behavior, upload cancellation, or
preview/right-panel routing. Mount browse surfaces and embedded SDK surfaces
must continue to provide their own action boundaries and local selection
scope.
