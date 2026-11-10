const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");
let csrfToken = "";
export const apiAssetUrl = (path: string) => API_BASE_URL + path;

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}
export function setCsrfToken(value: string) {
  csrfToken = value;
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(API_BASE_URL + path, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    if (
      response.status === 405 &&
      init.method?.toUpperCase() === "DELETE" &&
      path.startsWith("/platforms/")
    ) {
      throw new ApiError(
        "A API em execução está desatualizada e ainda não oferece exclusão de plataformas. Atualize e reinicie os serviços do projeto.",
        405,
      );
    }
    const body = (await response.json().catch(() => ({}))) as {
      detail?: string | { loc: string[]; msg: string }[];
    };
    const detail =
      typeof body.detail === "string"
        ? body.detail
        : Array.isArray(body.detail)
          ? body.detail
              .map((item) => item.loc.slice(1).join(".") + ": " + item.msg)
              .join("; ")
          : "Não foi possível concluir a operação.";
    throw new ApiError(detail, response.status);
  }
  return response.status === 204
    ? (undefined as T)
    : (response.json() as Promise<T>);
}
export const apiGet = <T>(path: string) => apiRequest<T>(path);
export const apiPost = <T>(
  path: string,
  body?: unknown,
  headers?: Record<string, string>,
) =>
  apiRequest<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
    headers,
  });
export const apiPut = <T>(path: string, body: unknown) =>
  apiRequest<T>(path, { method: "PUT", body: JSON.stringify(body) });
