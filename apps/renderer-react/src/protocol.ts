export type ContentType = "markdown" | "safe_html" | "sandbox_html";

export interface RenderPayload {
  contentType: ContentType;
  sourceContent: string;
  renderedHtml: string | null;
}

export const RENDERER_SOURCE = "pagedrop-renderer";

export interface ReadyMessage {
  source: typeof RENDERER_SOURCE;
  type: "ready";
}

export interface HeightMessage {
  source: typeof RENDERER_SOURCE;
  type: "height";
  height: number;
}

export interface RenderMessage {
  type: "render";
  payload: RenderPayload;
}

export function isRenderMessage(data: unknown): data is RenderMessage {
  return (
    typeof data === "object" &&
    data !== null &&
    (data as RenderMessage).type === "render" &&
    typeof (data as RenderMessage).payload === "object"
  );
}
