export class BatchOperationError extends Error {
  completedIds: string[];
  failedId: string;
  cause: unknown;

  constructor(params: {
    completedIds: string[];
    failedId: string;
    cause: unknown;
    message?: string;
    name?: string;
  }) {
    super(
      params.message ??
        "Batch operation stopped before completing the whole selection.",
    );
    this.name = params.name ?? "BatchOperationError";
    this.completedIds = params.completedIds;
    this.failedId = params.failedId;
    this.cause = params.cause;
  }
}
