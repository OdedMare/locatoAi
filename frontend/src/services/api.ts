/** Shared, traced JSON client for every browser-to-backend request. */

const SECRET_KEY = /(token|password|api[_-]?key|authorization|secret)/i;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly body: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const method = options?.method ?? "GET";
  const label = `${method} ${path}`;
  const started = performance.now();
  const quiet = method === "GET" && /^\/api\/query-runs\//.test(path);
  if (!quiet) console.debug(`[api] → ${label}`, requestBody(options));

  let response: Response;
  try {
    response = await fetch(path, withJsonHeaders(options));
  } catch (reason) {
    console.error(`[api] ✗ ${label} network error`, reason);
    throw reason;
  }

  const elapsed = performance.now() - started;
  const data = await responseData(response);
  if (!response.ok) {
    console.error(`[api] ✗ ${label} → ${response.status} (${elapsed.toFixed(0)}ms)`, {
      status: response.status,
      body: redact(data),
      sent: requestBody(options),
    });
    throw new ApiError(errorDetail(data, response.status), response.status, data);
  }
  if (!quiet || elapsed > 3000) {
    console.debug(`[api] ✓ ${label} → ${response.status} (${elapsed.toFixed(0)}ms)`, redact(data));
  }
  return data as T;
}

function withJsonHeaders(options?: RequestInit): RequestInit {
  const headers = new Headers(options?.headers);
  headers.set("Accept", "application/json");
  if (options?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return { ...options, headers, credentials: "same-origin" };
}

async function responseData(response: Response): Promise<unknown> {
  const raw = await response.text();
  if (!raw) return undefined;
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

function requestBody(options?: RequestInit): unknown {
  if (typeof options?.body !== "string") return undefined;
  try {
    return redact(JSON.parse(options.body));
  } catch {
    return options.body;
  }
}

function redact(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(redact);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [
    key,
    SECRET_KEY.test(key) && item ? "[redacted]" : redact(item),
  ]));
}

function errorDetail(data: unknown, status: number): string {
  const fallback = `הבקשה נכשלה (${status})`;
  const detail = (data as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail.trim() || fallback;
  if (Array.isArray(detail)) {
    const parts = detail.map(detailEntry).filter(Boolean);
    return parts.length ? parts.join("; ") : fallback;
  }
  if (detail && typeof detail === "object") return detailEntry(detail) || fallback;
  return fallback;
}

function detailEntry(entry: unknown): string {
  if (typeof entry === "string") return entry.trim();
  if (!entry || typeof entry !== "object") return "";
  const { loc, msg } = entry as { loc?: unknown; msg?: unknown };
  if (typeof msg !== "string") return "";
  const field = Array.isArray(loc)
    ? loc.filter((part) => part !== "body").join(" → ")
    : "";
  return field ? `${field}: ${msg}` : msg;
}
