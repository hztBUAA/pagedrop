export interface ApiErrorShape {
  status: number;
  detail: unknown;
}

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `request failed (${status})`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export class ApiClient {
  private sessionCookie: string | null = null;

  constructor(
    private readonly baseUrl: string,
    private readonly token: string,
  ) {}

  /** Whether a session cookie was captured from a prior login/register response. */
  hasSession(): boolean {
    return this.sessionCookie !== null;
  }

  private url(path: string): string {
    const base = this.baseUrl.replace(/\/+$/, "");
    return `${base}/api/v1${path}`;
  }

  private captureCookies(resp: Response): void {
    const getSetCookie = (resp.headers as { getSetCookie?: () => string[] }).getSetCookie;
    const raw = getSetCookie ? getSetCookie.call(resp.headers) : [];
    const single = resp.headers.get("set-cookie");
    const cookies = raw.length ? raw : single ? [single] : [];
    for (const c of cookies) {
      const pair = c.split(";")[0]?.trim();
      if (pair && pair.startsWith("pd_session=")) {
        this.sessionCookie = pair;
      }
    }
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    if (this.sessionCookie) headers.Cookie = this.sessionCookie;
    if (body !== undefined) headers["Content-Type"] = "application/json";

    let resp: Response;
    try {
      resp = await fetch(this.url(path), {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch (err) {
      throw new ApiError(0, `network error: ${(err as Error).message}`);
    }

    this.captureCookies(resp);
    const text = await resp.text();
    const data = text ? safeJson(text) : null;
    if (!resp.ok) {
      const detail = data && typeof data === "object" && "detail" in data ? data.detail : data;
      throw new ApiError(resp.status, detail ?? text);
    }
    return data as T;
  }

  get<T>(path: string): Promise<T> {
    return this.request<T>("GET", path);
  }

  post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>("POST", path, body);
  }

  del<T>(path: string): Promise<T> {
    return this.request<T>("DELETE", path);
  }

  async postForm<T>(path: string, form: FormData): Promise<T> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    let resp: Response;
    try {
      resp = await fetch(this.url(path), { method: "POST", headers, body: form });
    } catch (err) {
      throw new ApiError(0, `network error: ${(err as Error).message}`);
    }
    const text = await resp.text();
    const data = text ? safeJson(text) : null;
    if (!resp.ok) {
      const detail = data && typeof data === "object" && "detail" in data ? data.detail : data;
      throw new ApiError(resp.status, detail ?? text);
    }
    return data as T;
  }

  async getBytes(path: string): Promise<{ data: Buffer; contentType: string }> {
    const headers: Record<string, string> = {};
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    let resp: Response;
    try {
      resp = await fetch(this.url(path), { method: "GET", headers });
    } catch (err) {
      throw new ApiError(0, `network error: ${(err as Error).message}`);
    }
    if (!resp.ok) {
      const text = await resp.text();
      throw new ApiError(resp.status, safeJson(text) ?? text);
    }
    const buf = Buffer.from(await resp.arrayBuffer());
    return { data: buf, contentType: resp.headers.get("content-type") ?? "application/octet-stream" };
  }
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}
