import { APIError } from "@/features/api/APIError";
import {
  ensureCsrfCookie,
  fetchAPI,
  getCSRFToken,
} from "@/features/api/fetchApi";
import { baseApiUrl, isJson } from "@/features/api/utils";
import { getRuntimeConfig } from "@/features/config/runtimeConfig";
import { AppError } from "@/features/errors/AppError";
import { BatchDeleteError } from "@/features/errors/BatchDeleteError";
import { BatchOperationError } from "@/features/errors/BatchOperationError";
import { UploadError } from "@/features/errors/UploadError";
import i18n from "@/features/i18n/initI18n";
import { getOperationTimeBound } from "@/features/operations/timeBounds";
import {
  AbortableOperation,
  Driver,
  Entitlements,
  ItemFilters,
  UserFilters,
  PaginatedChildrenResult,
} from "../Driver";
import {
  DTODeleteInvitation,
  DTOCreateInvitation,
  DTOUpdateInvitation,
} from "../DTOs/InvitationDTO";
import {
  DTOCreateAccess,
  DTOUpdateLinkConfiguration,
} from "../DTOs/AccessesDTO";
import { DTOUpdateAccess } from "../DTOs/AccessesDTO";
import {
  Access,
  ApiConfig,
  APIList,
  Invitation,
  Item,
  ItemBreadcrumb,
  ItemTextContent,
  ItemType,
  User,
  WopiInfo,
  MountDiscovery,
  MountBrowseResponse,
  MountPreviewInfo,
  MountShareLinkCreateResponse,
  MountVirtualEntry,
} from "../types";
import { DTODeleteAccess } from "../DTOs/AccessesDTO";

export class StandardDriver extends Driver {
  private async runSequentialBatch(
    ids: string[],
    run: (id: string) => Promise<void>,
    createError: (params: {
      completedIds: string[];
      failedId: string;
      cause: unknown;
    }) => Error = (params) => new BatchOperationError(params),
  ): Promise<void> {
    const completedIds: string[] = [];

    for (const id of ids) {
      try {
        await run(id);
        completedIds.push(id);
      } catch (error) {
        if (completedIds.length > 0) {
          throw createError({
            completedIds,
            failedId: id,
            cause: error,
          });
        }
        throw error;
      }
    }
  }

  async getConfig(): Promise<ApiConfig> {
    const bounds = getOperationTimeBound("config_load");
    const response = await fetchAPI(`config/`, undefined, {
      timeoutMs: bounds.fail_ms,
    });
    const data = await response.json();
    return data;
  }

  async getItems(filters: ItemFilters = {}): Promise<PaginatedChildrenResult> {
    const params = {
      page: 1,
      page_size: 100,
      ...(filters ? filters : {}),
    };
    const response = await fetchAPI(`items/`, {
      params,
    });
    const data = await response.json();
    return {
      children: jsonToItems(data.results),
      pagination: {
        currentPage: filters.page ?? 1,
        totalCount: data.count,
        hasMore: data.next !== null,
      },
    };
  }

  async getItemBreadcrumb(id: string): Promise<ItemBreadcrumb[]> {
    const response = await fetchAPI(`items/${id}/breadcrumb/`);
    const data = await response.json();
    return data;
  }

  async searchItems(filters?: ItemFilters): Promise<Item[]> {
    const response = await fetchAPI(`items/search/`, {
      params: filters,
    });
    const data = await response.json();
    return jsonToItems(data.results);
  }

  async getTrashItems(filters?: ItemFilters): Promise<Item[]> {
    const response = await fetchAPI(`items/trashbin/`, {
      params: { ...filters, page_size: 200 },
    });
    const data = await response.json();
    return jsonToItems(data.results);
  }

  async getItem(id: string): Promise<Item> {
    const response = await fetchAPI(`items/${id}/`);
    const data = await response.json();
    return jsonToItem(data);
  }

  async updateItem(item: Partial<Item>): Promise<Item> {
    const response = await fetchAPI(`items/${item.id}/`, {
      method: "PATCH",
      body: JSON.stringify(item),
    });
    const data = await response.json();
    return jsonToItem(data);
  }

  async restoreItems(ids: string[]): Promise<void> {
    await this.runSequentialBatch(ids, async (id) => {
      await fetchAPI(
        `items/${id}/restore/`,
        {
          method: "POST",
        },
        {
          redirectOn40x: false,
        },
      );
    });
  }

  async getUsers(filters?: UserFilters): Promise<User[]> {
    const response = await fetchAPI(`users/`, {
      params: filters,
    });
    const data = await response.json();
    return data;
  }

  async updateUser(payload: Partial<User> & { id: string }): Promise<User> {
    const response = await fetchAPI(`users/${payload.id}/`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    return data;
  }

  async getChildren(
    id: string,
    filters?: ItemFilters,
  ): Promise<PaginatedChildrenResult> {
    const params = {
      page: 1,
      page_size: filters?.page_size || 200,
      ...(filters ? filters : {}),
    };

    const response = await fetchAPI(`items/${id}/children/`, {
      params,
    });
    const data = await response.json();

    return {
      children: jsonToItems(data.results),
      pagination: {
        currentPage: params.page,
        totalCount: data.count,
        hasMore: data.next !== null,
      },
    };
  }

  async getTree(id: string): Promise<Item> {
    const response = await fetchAPI(`items/${id}/tree/`);
    const data = await response.json();
    return jsonToItem(data);
  }

  async moveItem(id: string, parentId?: string): Promise<void> {
    const payload = {
      ...(parentId ? { target_item_id: parentId } : {}),
    };
    await fetchAPI(
      `items/${id}/move/`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      {
        redirectOn40x: false,
      },
    );
  }

  async getItemAccesses(itemId: string): Promise<Access[]> {
    const response = await fetchAPI(`items/${itemId}/accesses/`);
    const data = await response.json();
    return data;
  }

  async createAccess(data: DTOCreateAccess): Promise<void> {
    await fetchAPI(`items/${data.itemId}/accesses/`, {
      method: "POST",
      body: JSON.stringify({
        user_id: data.userId,
        role: data.role,
      }),
    });
  }

  async deleteAccess(payload: DTODeleteAccess): Promise<void> {
    await fetchAPI(`items/${payload.itemId}/accesses/${payload.accessId}/`, {
      method: "DELETE",
    });
  }

  async updateLinkConfiguration(
    payload: DTOUpdateLinkConfiguration,
  ): Promise<void> {
    const { itemId, ...rest } = payload;
    await fetchAPI(`items/${itemId}/link-configuration/`, {
      method: "PUT",
      body: JSON.stringify(rest),
    });
  }

  async updateAccess({
    itemId,
    accessId,
    ...payload
  }: DTOUpdateAccess): Promise<Access | void> {
    const response = await fetchAPI(`items/${itemId}/accesses/${accessId}/`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });

    if (response.status === 204) {
      return;
    }

    const data = await response.json();
    return data;
  }

  async createInvitation(payload: DTOCreateInvitation): Promise<Invitation> {
    const response = await fetchAPI(`items/${payload.itemId}/invitations/`, {
      method: "POST",
      body: JSON.stringify({
        email: payload.email,
        role: payload.role,
      }),
    });
    const data = await response.json();
    return data;
  }

  async deleteInvitation(payload: DTODeleteInvitation): Promise<void> {
    await fetchAPI(
      `items/${payload.itemId}/invitations/${payload.invitationId}/`,
      {
        method: "DELETE",
      },
    );
  }

  async updateInvitation(payload: DTOUpdateInvitation): Promise<Invitation> {
    const response = await fetchAPI(
      `items/${payload.itemId}/invitations/${payload.invitationId}/`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
      },
    );
    const data = await response.json();
    return data;
  }

  async getItemInvitations(itemId: string): Promise<APIList<Invitation>> {
    const response = await fetchAPI(`items/${itemId}/invitations/`);
    const data = await response.json();
    return data;
  }

  async moveItems(ids: string[], parentId?: string): Promise<void> {
    await this.runSequentialBatch(ids, async (id) => {
      await this.moveItem(id, parentId);
    });
  }

  async createFolder(data: {
    title: string;
    parentId?: string;
  }): Promise<Item> {
    const { parentId, ...rest } = data;
    const url = parentId ? `items/${parentId}/children/` : `items/`;
    const response = await fetchAPI(url, {
      method: "POST",
      body: JSON.stringify({
        ...rest,
        type: ItemType.FOLDER,
      }),
    });
    const item = await response.json();
    return jsonToItem(item);
  }

  async createWorkspace(data: {
    title: string;
    description: string;
  }): Promise<Item> {
    const response = await fetchAPI(`items/`, {
      method: "POST",
      body: JSON.stringify({
        ...data,
        type: ItemType.FOLDER,
      }),
    });
    const item = await response.json();
    return jsonToItem(item);
  }

  async updateWorkspace(item: Partial<Item>): Promise<Item> {
    return this.updateItem(item);
  }

  async deleteWorkspace(id: string): Promise<void> {
    return this.deleteItems([id]);
  }

  async duplicateItem(id: string): Promise<Item> {
    const response = await fetchAPI(`items/${id}/duplicate/`, {
      method: "POST",
    });
    const data = await response.json();
    return jsonToItem(data);
  }

  async getRecentItems(
    filters?: ItemFilters,
  ): Promise<PaginatedChildrenResult> {
    const response = await fetchAPI(`items/recents/`, {
      params: { ...filters, page_size: 200 },
    });
    const data = await response.json();
    return {
      children: jsonToItems(data.results),
      pagination: {
        currentPage: filters?.page ?? 1,
        totalCount: data.count,
        hasMore: data.next !== null,
      },
    };
  }

  async getFavoriteItems(
    filters?: ItemFilters,
  ): Promise<PaginatedChildrenResult> {
    const response = await fetchAPI(`items/favorite_list/`, {
      params: { ...filters, page_size: 200 },
    });

    const data = await response.json();
    return {
      children: jsonToItems(data.results),
      pagination: {
        currentPage: filters?.page ?? 1,
        totalCount: data.count,
        hasMore: data.next !== null,
      },
    };
  }

  async createFavoriteItem(itemId: string): Promise<void> {
    await fetchAPI(`items/${itemId}/favorite/`, {
      method: "POST",
    });
  }

  async deleteFavoriteItem(itemId: string): Promise<void> {
    await fetchAPI(`items/${itemId}/favorite/`, {
      method: "DELETE",
    });
  }

  createFile(data: {
    parentId?: string;
    file: File;
    filename: string;
    progressHandler?: (progress: number) => void;
  }): AbortableOperation<Item> {
    const config = getRuntimeConfig();
    const createBounds = getOperationTimeBound("upload_create", config);
    const uploadPutBounds = getOperationTimeBound("upload_put", config);
    const finalizeBounds = getOperationTimeBound("upload_finalize", config);

    let aborted = false;
    let abortUpload: (() => void) | undefined;
    const abortController = new AbortController();
    const buildAbortError = () =>
      new DOMException("Upload cancelled", "AbortError");
    const throwIfAborted = () => {
      if (aborted) {
        throw buildAbortError();
      }
    };

    const abort = () => {
      aborted = true;
      abortUpload?.();
      abortController.abort();
    };

    const promise = (async () => {
      const { parentId, file, progressHandler, ...rest } = data;
      const url = parentId ? `items/${parentId}/children/` : `items/`;
      const response = await fetchAPI(
        url,
        {
          method: "POST",
          body: JSON.stringify({
            type: ItemType.FILE,
            ...rest,
          }),
          signal: abortController.signal,
        },
        {
          // When entitlements are falsy, the backend returns a 403 error.
          // We don't want to redirect to the login page in this case, instead
          // we want to show an error.
          redirectOn40x: false,
          timeoutMs: createBounds.fail_ms,
        },
      );
      const item = jsonToItem(await response.json());
      if (!item.policy) {
        throw new AppError(i18n.t("api.error.unexpected"));
      }

      throwIfAborted();

      // We want the upload progress ( that goes from 0 to 100) to be proxied to the progress handler ( that goes from 0 to 95)
      // So the progression indicator still shows leave a 5% gap before the upload-ended is called.
      // We want to wait until the upload-ended endpoint is called.
      const progressHandlerProxy = (progress: number) => {
        const proxyScale = 90;
        const proxiedProgress = (progress * proxyScale) / 100;
        progressHandler?.(proxiedProgress);
      };

      const upload = uploadFile(
        item.policy,
        file,
        (progress) => progressHandlerProxy(progress),
        uploadPutBounds.fail_ms,
        { itemId: item.id },
      );
      abortUpload = upload.abort;

      try {
        await upload.promise;
      } catch (error) {
        if (
          aborted ||
          (error instanceof DOMException && error.name === "AbortError")
        ) {
          throw buildAbortError();
        }
        if (error instanceof UploadError) {
          throw error;
        }
        throw new UploadError({
          message: i18n.t("explorer.actions.upload.errors.put_failed"),
          kind: "put_failed",
          nextAction: "retry",
          itemId: item.id,
        });
      }

      throwIfAborted();

      try {
        await fetchAPI(
          `items/${item.id}/upload-ended/`,
          { method: "POST", signal: abortController.signal },
          { redirectOn40x: false, timeoutMs: finalizeBounds.fail_ms },
        );
      } catch (error) {
        if (
          aborted ||
          (error instanceof DOMException && error.name === "AbortError")
        ) {
          throw buildAbortError();
        }
        if (error instanceof UploadError) {
          throw error;
        }
        throw new UploadError({
          message: i18n.t("explorer.actions.upload.errors.finalize_failed"),
          kind: "finalize_failed",
          nextAction: "retry",
          itemId: item.id,
        });
      }

      progressHandler?.(100);

      return item;
    })();

    return { promise, abort };
  }

  async reinitiateFileUpload(data: {
    itemId: string;
    file: File;
    filename: string;
    progressHandler?: (progress: number) => void;
  }): Promise<void> {
    const config = getRuntimeConfig();
    const createBounds = getOperationTimeBound("upload_create", config);
    const uploadPutBounds = getOperationTimeBound("upload_put", config);
    const finalizeBounds = getOperationTimeBound("upload_finalize", config);

    const progressHandlerProxy = (progress: number) => {
      if (progress === 100) {
        return;
      }
      data.progressHandler?.(progress);
    };

    let policy: string;
    try {
      const response = await fetchAPI(
        `items/${data.itemId}/upload-policy/`,
        { method: "POST" },
        { redirectOn40x: false, timeoutMs: createBounds.fail_ms },
      );
      const payload = await response.json();
      policy = payload?.policy;
    } catch {
      throw new UploadError({
        message: i18n.t("explorer.actions.upload.errors.reinitiate_failed"),
        kind: "create_failed",
        nextAction: "contact_admin",
        itemId: data.itemId,
      });
    }

    if (!policy) {
      throw new UploadError({
        message: i18n.t("explorer.actions.upload.errors.reinitiate_failed"),
        kind: "create_failed",
        nextAction: "contact_admin",
        itemId: data.itemId,
      });
    }

    await uploadFile(
      policy,
      data.file,
      (progress) => progressHandlerProxy(progress),
      uploadPutBounds.fail_ms,
      { itemId: data.itemId },
    ).promise;

    await fetchAPI(
      `items/${data.itemId}/upload-ended/`,
      { method: "POST" },
      { redirectOn40x: false, timeoutMs: finalizeBounds.fail_ms },
    );

    data.progressHandler?.(100);
  }

  async createOdfDocument(data: {
    parentId?: string;
    kind: "odt" | "ods" | "odp";
    filename: string;
  }): Promise<Item> {
    const { parentId, kind, filename } = data;
    const response = await fetchAPI(`items/new-odf/`, {
      method: "POST",
      body: JSON.stringify({
        parent_id: parentId ?? null,
        kind,
        filename,
      }),
    });
    const item = await response.json();
    return jsonToItem(item);
  }

  async createNewFile(data: {
    parentId?: string;
    filenameStem: string;
    extension: string;
    kind?: "text" | "sheet" | "slide";
  }): Promise<Item> {
    const response = await fetchAPI(`items/new-file/`, {
      method: "POST",
      body: JSON.stringify({
        parent_id: data.parentId ?? null,
        filename_stem: data.filenameStem,
        extension: data.extension,
        kind: data.kind ?? null,
      }),
    });
    const item = await response.json();
    return jsonToItem(item);
  }

  async deleteItems(ids: string[]): Promise<void> {
    await this.runSequentialBatch(
      ids,
      async (id) => {
        await fetchAPI(
          `items/${id}/`,
          {
            method: "DELETE",
          },
          {
            redirectOn40x: false,
          },
        );
      },
      (params) => new BatchDeleteError(params),
    );
  }

  async hardDeleteItems(ids: string[]): Promise<void> {
    await this.runSequentialBatch(ids, async (id) => {
      await fetchAPI(
        `items/${id}/hard-delete/`,
        {
          method: "DELETE",
        },
        {
          redirectOn40x: false,
        },
      );
    });
  }

  async getWopiInfo(itemId: string): Promise<WopiInfo> {
    const config = getRuntimeConfig();
    const bounds = getOperationTimeBound("wopi_info", config);
    const response = await fetchAPI(`items/${itemId}/wopi/`, undefined, {
      timeoutMs: bounds.fail_ms,
    });
    try {
      return await response.json();
    } catch {
      throw new APIError(response.status);
    }
  }

  async getItemText(itemId: string): Promise<ItemTextContent> {
    const response = await fetchAPI(`items/${itemId}/text/`, undefined, {
      redirectOn40x: false,
    });
    const data = (await response.json()) as ItemTextContent;
    const etag = response.headers.get("ETag") ?? data.etag ?? "";
    return { ...data, etag };
  }

  async saveItemText(params: {
    itemId: string;
    content: string;
    etag: string;
  }): Promise<{ etag: string | null }> {
    const response = await fetchAPI(`items/${params.itemId}/text/`, {
      method: "PUT",
      headers: { "If-Match": params.etag },
      body: JSON.stringify({ content: params.content }),
    });
    let bodyEtag: string | null = null;
    try {
      // Body is optional; header is the source of truth.
      const data = (await response.json()) as { etag?: string };
      bodyEtag = data?.etag ?? null;
    } catch {
      bodyEtag = null;
    }
    return { etag: response.headers.get("ETag") ?? bodyEtag };
  }

  async getEntitlements(): Promise<Entitlements> {
    const response = await fetchAPI(`entitlements/`);
    const data = await response.json();
    return data;
  }

  async confirmUserReconciliation(
    userType: "active" | "inactive",
    confirmationId: string,
  ): Promise<void> {
    await fetchAPI(`user-reconciliations/${userType}/${confirmationId}/`);
  }

  async getMountsDiscovery(): Promise<MountDiscovery[]> {
    const response = await fetchAPI(`mounts/`);
    const data = await response.json();
    return data;
  }

  async browseMount(params: {
    mountId: string;
    path?: string;
    limit?: number;
    offset?: number;
  }): Promise<MountBrowseResponse> {
    const path = params.path ?? "/";
    const limit = params.limit ?? 20;
    const offset = params.offset ?? 0;

    const query = new URLSearchParams({
      path,
      limit: String(limit),
      offset: String(offset),
    });
    const response = await fetchAPI(
      `mounts/${params.mountId}/browse/?${query}`,
    );
    const data = await response.json();
    return data;
  }

  async getMountPreviewInfo(params: {
    mountId: string;
    path: string;
  }): Promise<MountPreviewInfo> {
    const response = await fetchAPI(`mounts/${params.mountId}/preview-info/`, {
      params: { path: params.path },
    });
    const data = await response.json();
    return data;
  }

  async getMountText(params: {
    mountId: string;
    path: string;
  }): Promise<ItemTextContent> {
    const response = await fetchAPI(
      `mounts/${params.mountId}/text/`,
      {
        params: { path: params.path },
      },
      {
        redirectOn40x: false,
      },
    );
    const data = (await response.json()) as ItemTextContent;
    const etag = response.headers.get("ETag") ?? data.etag ?? "";
    return { ...data, etag };
  }

  async saveMountText(params: {
    mountId: string;
    path: string;
    content: string;
    etag: string;
  }): Promise<{ etag: string | null }> {
    const response = await fetchAPI(
      `mounts/${params.mountId}/text/`,
      {
        method: "PUT",
        params: { path: params.path },
        headers: { "If-Match": params.etag },
        body: JSON.stringify({ content: params.content }),
      },
      {
        redirectOn40x: false,
      },
    );
    let bodyEtag: string | null = null;
    try {
      const data = (await response.json()) as { etag?: string };
      bodyEtag = data?.etag ?? null;
    } catch {
      bodyEtag = null;
    }
    return { etag: response.headers.get("ETag") ?? bodyEtag };
  }

  async createMountShareLink(params: {
    mountId: string;
    path: string;
  }): Promise<MountShareLinkCreateResponse> {
    const response = await fetchAPI(`mounts/${params.mountId}/share-links/`, {
      method: "POST",
      body: JSON.stringify({ path: params.path }),
    });
    const data = await response.json();
    return data;
  }

  async duplicateMountEntry(params: {
    mountId: string;
    path: string;
  }): Promise<MountVirtualEntry> {
    const response = await fetchAPI(
      `mounts/${params.mountId}/duplicate/`,
      {
        method: "POST",
        params: { path: params.path },
      },
      { redirectOn40x: false },
    );
    const data = await response.json();
    return data;
  }

  async createMountFolder(params: {
    mountId: string;
    path: string;
    name: string;
    reuseExisting?: boolean;
  }): Promise<MountVirtualEntry> {
    const response = await fetchAPI(
      `mounts/${params.mountId}/folders/`,
      {
        method: "POST",
        params: { path: params.path },
        body: JSON.stringify({
          name: params.name,
          reuse_existing: params.reuseExisting ?? false,
        }),
      },
      { redirectOn40x: false },
    );
    const data = await response.json();
    return data;
  }

  async renameMountEntry(params: {
    mountId: string;
    path: string;
    name: string;
  }): Promise<MountVirtualEntry> {
    const response = await fetchAPI(
      `mounts/${params.mountId}/rename/`,
      {
        method: "POST",
        params: { path: params.path },
        body: JSON.stringify({ name: params.name }),
      },
      { redirectOn40x: false },
    );
    const data = await response.json();
    return data;
  }

  async moveMountEntry(params: {
    mountId: string;
    path: string;
    targetPath: string;
  }): Promise<MountVirtualEntry> {
    const response = await fetchAPI(
      `mounts/${params.mountId}/move/`,
      {
        method: "POST",
        params: { path: params.path },
        body: JSON.stringify({ target_path: params.targetPath }),
      },
      { redirectOn40x: false },
    );
    const data = await response.json();
    return data;
  }

  async deleteMountEntry(params: {
    mountId: string;
    path: string;
  }): Promise<void> {
    await fetchAPI(
      `mounts/${params.mountId}/delete/`,
      {
        method: "DELETE",
        params: { path: params.path },
      },
      { redirectOn40x: false },
    );
  }

  async getMountWopiInfo(params: {
    mountId: string;
    path: string;
  }): Promise<WopiInfo> {
    const config = getRuntimeConfig();
    const bounds = getOperationTimeBound("wopi_info", config);
    const response = await fetchAPI(
      `mounts/${params.mountId}/wopi/`,
      { params: { path: params.path } },
      { timeoutMs: bounds.fail_ms, redirectOn40x: false },
    );
    const data = await response.json();
    return data;
  }

  async uploadMountFile(params: {
    mountId: string;
    path: string;
    file: File;
    progressHandler?: (progress: number) => void;
  }): Promise<{ mount_id: string; normalized_path: string }> {
    const uploadUrl = new URL(
      `${baseApiUrl("1.0")}mounts/${params.mountId}/upload/`,
    );
    uploadUrl.searchParams.set("path", params.path);
    const data = await uploadMountFileXHR(
      uploadUrl.toString(),
      params.file,
      params.progressHandler,
    );
    return data;
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const jsonToItems = (data: any[]): Item[] => {
  return data.map((v) => jsonToItem(v));
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const jsonToItem = (data: any): Item => {
  const item = {
    ...data,
    updated_at: new Date(data.updated_at),
  };
  if (data.children) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    item.children = data.children.map((v: any) => jsonToItem(v));
  }
  return item;
};

/**
 * Upload a file, using XHR so we can report on progress through a handler.
 * @param url The URL to POST the file to.
 * @param formData The multi-part request form data body to send (includes the file).
 * @param progressHandler A handler that receives progress updates as a single integer `0 <= x <= 100`.
 */
export const uploadFile = (
  url: string,
  file: File,
  progressHandler: (progress: number) => void,
  timeoutMs?: number,
  opts?: { itemId?: string },
): AbortableOperation<boolean> => {
  const xhr = new XMLHttpRequest();
  const promise = new Promise<boolean>((resolve, reject) => {
    xhr.open("PUT", url);
    xhr.setRequestHeader("X-amz-acl", "private");
    xhr.setRequestHeader("Content-Type", file.type);

    if (timeoutMs !== undefined) {
      xhr.timeout = timeoutMs;
    }

    const rejectWith = (params: {
      message: string;
      kind: "put_failed" | "timeout";
      nextAction: "retry" | "reinitiate" | "contact_admin";
    }) => {
      reject(
        new UploadError({
          message: params.message,
          kind: params.kind,
          nextAction: params.nextAction,
          itemId: opts?.itemId,
        }),
      );
    };

    xhr.addEventListener("error", () =>
      rejectWith({
        message: i18n.t("explorer.actions.upload.errors.put_failed"),
        kind: "put_failed",
        nextAction: "retry",
      }),
    );
    xhr.addEventListener("abort", () =>
      reject(new DOMException("Upload cancelled", "AbortError")),
    );
    xhr.addEventListener("timeout", () => {
      rejectWith({
        message: i18n.t("explorer.actions.upload.errors.timeout"),
        kind: "timeout",
        nextAction: "retry",
      });
    });

    xhr.addEventListener("readystatechange", () => {
      if (xhr.readyState === 4) {
        if (xhr.status === 200) {
          // Make sure to always set the progress to 100% when the upload is done.
          // Because 'progress' event listener is not called when the file size is 0.
          progressHandler(100);
          return resolve(true);
        }
        if (xhr.status === 0) {
          return;
        }
        const status = xhr.status;
        if (status === 400 || status === 403) {
          return rejectWith({
            message: i18n.t("explorer.actions.upload.errors.policy_expired"),
            kind: "put_failed",
            nextAction: "reinitiate",
          });
        }
        if (status >= 500) {
          return rejectWith({
            message: i18n.t(
              "explorer.actions.upload.errors.storage_unavailable",
            ),
            kind: "put_failed",
            nextAction: "retry",
          });
        }
        return rejectWith({
          message: i18n.t("explorer.actions.upload.errors.put_failed"),
          kind: "put_failed",
          nextAction: "retry",
        });
      }
    });

    xhr.upload.addEventListener("progress", (progressEvent) => {
      if (progressEvent.lengthComputable) {
        progressHandler(
          Math.floor((progressEvent.loaded / progressEvent.total) * 100),
        );
      }
    });

    xhr.send(file);
  });

  return { promise, abort: () => xhr.abort() };
};

const uploadMountFileXHR = async (
  url: string,
  file: File,
  progressHandler?: (progress: number) => void,
): Promise<{ mount_id: string; normalized_path: string }> => {
  if (!getCSRFToken()) {
    await ensureCsrfCookie();
  }
  const csrfToken = getCSRFToken();

  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", file, file.name);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.withCredentials = true;

    if (csrfToken) {
      xhr.setRequestHeader("X-CSRFToken", csrfToken);
    }

    const rejectUnexpected = () => {
      reject(new AppError(i18n.t("api.error.unexpected")));
    };

    xhr.addEventListener("error", rejectUnexpected);
    xhr.addEventListener("abort", rejectUnexpected);

    xhr.addEventListener("readystatechange", () => {
      if (xhr.readyState !== 4) {
        return;
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        progressHandler?.(100);
        const responseText = xhr.responseText;
        if (!responseText) {
          rejectUnexpected();
          return;
        }
        resolve(JSON.parse(responseText));
        return;
      }

      const responseText = xhr.responseText;
      if (responseText && isJson(responseText)) {
        reject(new APIError(xhr.status, JSON.parse(responseText)));
        return;
      }

      reject(new APIError(xhr.status));
    });

    if (progressHandler) {
      xhr.upload.addEventListener("progress", (progressEvent) => {
        if (progressEvent.lengthComputable) {
          progressHandler(
            Math.floor((progressEvent.loaded / progressEvent.total) * 100),
          );
        }
      });
    }

    xhr.send(formData);
  });
};
