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

/** Renderer -> parent: the user selected text in the content (empty quote = cleared). */
export interface SelectionMessage {
  source: typeof RENDERER_SOURCE;
  type: "selection";
  quote: string;
  prefix: string;
  suffix: string;
}

/** Renderer -> parent: the user clicked on a highlighted anchor. */
export interface AnchorClickMessage {
  source: typeof RENDERER_SOURCE;
  type: "anchor-click";
  commentId: string;
}

export type OutboundMessage =
  | ReadyMessage
  | HeightMessage
  | SelectionMessage
  | AnchorClickMessage;

export interface RenderMessage {
  type: "render";
  payload: RenderPayload;
}

/** parent -> renderer: anchors to highlight in the content. */
export interface HighlightAnchor {
  id: string;
  quote: string;
  prefix: string;
  suffix: string;
}

export interface HighlightsMessage {
  type: "highlights";
  anchors: HighlightAnchor[];
}

/** parent -> renderer: scroll to and emphasize a given anchor (null clears focus). */
export interface FocusAnchorMessage {
  type: "focus-anchor";
  id: string | null;
}

export function isRenderMessage(data: unknown): data is RenderMessage {
  return (
    typeof data === "object" &&
    data !== null &&
    (data as RenderMessage).type === "render" &&
    typeof (data as RenderMessage).payload === "object"
  );
}

export function isHighlightsMessage(data: unknown): data is HighlightsMessage {
  return (
    typeof data === "object" &&
    data !== null &&
    (data as HighlightsMessage).type === "highlights" &&
    Array.isArray((data as HighlightsMessage).anchors)
  );
}

export function isFocusAnchorMessage(data: unknown): data is FocusAnchorMessage {
  return (
    typeof data === "object" &&
    data !== null &&
    (data as FocusAnchorMessage).type === "focus-anchor"
  );
}
