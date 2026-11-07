export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

function errorText(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value))
    return value
      .map((item) => {
        if (typeof item === "object" && item !== null && "msg" in item) {
          const record = item as { loc?: unknown[]; msg: string };
          return `${record.loc?.filter((part) => part !== "body").join(".") || "Request"}: ${record.msg}`;
        }
        return String(item);
      })
      .join("; ");
  return "The request could not be completed.";
}

export async function request<T>(
  path: string,
  token: string | null,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body) headers.set("Content-Type", "application/json");
  const response = await fetch(`/api${path}`, {
    ...options,
    headers,
    signal: options.signal ?? AbortSignal.timeout(25000),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(
      errorText(body.detail ?? body.error ?? response.statusText),
      response.status,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function downloadRun(
  id: string,
  format: "json" | "csv",
  token: string,
): Promise<void> {
  const response = await fetch(
    `/api/experiments/${id}/export?format=${format}`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  if (!response.ok)
    throw new ApiError(
      "Export could not be downloaded. Please try again.",
      response.status,
    );
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `intentional-agent-${id}.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function message(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
}
