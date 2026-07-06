type EventListener = (event?: unknown) => void;

type FakeXhrBehavior = {
  onSend?: (xhr: FakeXMLHttpRequest) => void;
};

class FakeUploadTarget {
  private listeners = new Map<string, EventListener[]>();

  addEventListener(event: string, listener: EventListener) {
    const current = this.listeners.get(event) ?? [];
    current.push(listener);
    this.listeners.set(event, current);
  }

  dispatch(event: string, payload?: unknown) {
    const current = this.listeners.get(event) ?? [];
    current.forEach((listener) => listener(payload));
  }
}

export class FakeXMLHttpRequest {
  static queue: FakeXhrBehavior[] = [];
  static instances: FakeXMLHttpRequest[] = [];

  static enqueue(behavior: FakeXhrBehavior) {
    this.queue.push(behavior);
  }

  static reset() {
    this.queue = [];
    this.instances = [];
  }

  readonly upload = new FakeUploadTarget();

  method = "";
  url = "";
  sentBody: unknown;
  headers: Record<string, string> = {};
  timeout = 0;
  readyState = 0;
  status = 0;
  responseText = "";
  withCredentials = false;

  private readonly listeners = new Map<string, EventListener[]>();
  private readonly behavior: FakeXhrBehavior;

  constructor() {
    this.behavior = FakeXMLHttpRequest.queue.shift() ?? {};
    FakeXMLHttpRequest.instances.push(this);
  }

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }

  setRequestHeader(name: string, value: string) {
    this.headers[name] = value;
  }

  addEventListener(event: string, listener: EventListener) {
    const current = this.listeners.get(event) ?? [];
    current.push(listener);
    this.listeners.set(event, current);
  }

  send(body: unknown) {
    this.sentBody = body;
    this.behavior.onSend?.(this);
  }

  abort() {
    this.status = 0;
    this.readyState = 4;
    this.emit("abort");
    this.emit("readystatechange");
  }

  emit(event: string, payload?: unknown) {
    const current = this.listeners.get(event) ?? [];
    current.forEach((listener) => listener(payload));
  }

  emitUploadProgress(loaded: number, total: number, lengthComputable = true) {
    this.upload.dispatch("progress", {
      lengthComputable,
      loaded,
      total,
    });
  }

  complete(params: { status: number; responseText?: string }) {
    this.status = params.status;
    this.responseText = params.responseText ?? "";
    this.readyState = 4;
    this.emit("readystatechange");
  }
}
