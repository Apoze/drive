import { BatchOperationError } from "./BatchOperationError";

export class BatchDeleteError extends BatchOperationError {
  constructor(params: {
    completedIds: string[];
    failedId: string;
    cause: unknown;
  }) {
    super({
      ...params,
      message: "Bulk delete stopped before completing the whole selection.",
      name: "BatchDeleteError",
    });
  }
}
