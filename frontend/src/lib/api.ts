import { serviceErrors } from "@/lib/service-errors";
import { z } from "zod";
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
const messages: Record<number, string> = {
  401: "Your demo session has expired. Sign in again.",
  403: "This action is not authorized for this workspace.",
  404: "This item is unavailable or has been deleted.",
  409: "This file is already in your knowledge base.",
  413: "The file exceeds the upload limit.",
  422: "Check your input and try again.",
  429: "Too many requests. Please wait before trying again.",
  502: "The backend returned an unavailable or invalid response.",
  503: "The service or its provider is unavailable. Try again shortly.",
  504: "The operation timed out. Check the document list before retrying an upload.",
};
export function errorMessage(status: number) {
  return (
    messages[status] || "The request could not be completed. Please try again."
  );
}
export async function api<T>(
  path: string,
  schema: z.ZodType<T>,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`/api/bff/${path}`, {
    ...options,
    cache: "no-store",
    credentials: "same-origin",
    headers: {
      ...(options?.body && !(options.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...options?.headers,
    },
  });
  if (!response.ok) {
    const failure = await response.json().catch(() => null);
    const code = failure?.code;
    const message =
      typeof code === "string" && Object.hasOwn(serviceErrors, code)
        ? serviceErrors[code]
        : errorMessage(response.status);
    throw new ApiError(response.status, message);
  }
  const parsed = schema.safeParse(await response.json());
  if (!parsed.success)
    throw new ApiError(502, "The service response did not match its contract.");
  return parsed.data;
}
export function upload(
  file: File,
  onProgress: (n: number) => void,
  schema: z.ZodType,
) {
  return new Promise<unknown>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/bff/documents/upload");
    xhr.timeout = 180000;
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable)
        onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(new ApiError(xhr.status, errorMessage(xhr.status)));
        return;
      }
      try {
        resolve(schema.parse(JSON.parse(xhr.responseText)));
      } catch {
        reject(new ApiError(502, "Invalid upload response."));
      }
    };
    xhr.onerror = () =>
      reject(
        new ApiError(
          503,
          "Connection lost. Check the document list before retrying.",
        ),
      );
    xhr.ontimeout = () => reject(new ApiError(504, errorMessage(504)));
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

export async function apiDelete(path: string): Promise<void> {
  const response = await fetch(`/api/bff/${path}`, {
    method: "DELETE",
    cache: "no-store",
    credentials: "same-origin",
  });
  if (!response.ok)
    throw new ApiError(response.status, errorMessage(response.status));
}
