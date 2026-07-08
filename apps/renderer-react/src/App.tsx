import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import DOMPurify from "dompurify";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { locateQuote, selectionToAnchor } from "./anchor";
import {
  isFocusAnchorMessage,
  isHighlightsMessage,
  isRenderMessage,
  RENDERER_SOURCE,
  type HighlightAnchor,
  type OutboundMessage,
  type RenderPayload,
} from "./protocol";

function postToParent(msg: OutboundMessage) {
  if (window.parent && window.parent !== window) {
    window.parent.postMessage(msg, "*");
  }
}

// CSS Custom Highlight API: highlight anchored ranges without mutating the
// React-controlled DOM. Returns null when the browser lacks the API.
type HighlightCtor = new (...ranges: Range[]) => unknown;
function highlightApi(): { registry: Map<string, unknown>; Ctor: HighlightCtor } | null {
  const g = window as unknown as {
    CSS?: { highlights?: Map<string, unknown> };
    Highlight?: HighlightCtor;
  };
  if (g.CSS?.highlights && g.Highlight) return { registry: g.CSS.highlights, Ctor: g.Highlight };
  return null;
}

export default function App() {
  const [payload, setPayload] = useState<RenderPayload | null>(
    (window as unknown as { __PAGEDROP_PAYLOAD__?: RenderPayload }).__PAGEDROP_PAYLOAD__ ?? null,
  );
  const [anchors, setAnchors] = useState<HighlightAnchor[]>([]);
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const rangesRef = useRef<Map<string, Range>>(new Map());

  useEffect(() => {
    function onMessage(e: MessageEvent) {
      if (isRenderMessage(e.data)) {
        setPayload(e.data.payload);
      } else if (isHighlightsMessage(e.data)) {
        setAnchors(e.data.anchors);
      } else if (isFocusAnchorMessage(e.data)) {
        setFocusedId(e.data.id);
      }
    }
    window.addEventListener("message", onMessage);
    postToParent({ source: RENDERER_SOURCE, type: "ready" });
    return () => window.removeEventListener("message", onMessage);
  }, []);

  // Selection -> parent. mouseup finalizes a selection (empty = cleared).
  useEffect(() => {
    function onMouseUp() {
      const root = rootRef.current;
      const sel = window.getSelection();
      if (!root || !sel) return;
      const anchor = selectionToAnchor(root, sel);
      if (anchor) {
        postToParent({ source: RENDERER_SOURCE, type: "selection", ...anchor });
      } else {
        postToParent({ source: RENDERER_SOURCE, type: "selection", quote: "", prefix: "", suffix: "" });
      }
    }
    document.addEventListener("mouseup", onMouseUp);
    return () => document.removeEventListener("mouseup", onMouseUp);
  }, []);

  // Click on a highlighted range -> parent (best-effort hit test).
  useEffect(() => {
    function onClick(e: MouseEvent) {
      const map = rangesRef.current;
      if (map.size === 0) return;
      const doc = document as Document & {
        caretRangeFromPoint?: (x: number, y: number) => Range | null;
        caretPositionFromPoint?: (
          x: number,
          y: number,
        ) => { offsetNode: Node; offset: number } | null;
      };
      let container: Node | null = null;
      let offset = 0;
      if (doc.caretRangeFromPoint) {
        const c = doc.caretRangeFromPoint(e.clientX, e.clientY);
        if (c) {
          container = c.startContainer;
          offset = c.startOffset;
        }
      } else if (doc.caretPositionFromPoint) {
        const pos = doc.caretPositionFromPoint(e.clientX, e.clientY);
        if (pos) {
          container = pos.offsetNode;
          offset = pos.offset;
        }
      }
      if (!container) return;
      for (const [id, r] of map) {
        if (r.isPointInRange(container, offset)) {
          postToParent({ source: RENDERER_SOURCE, type: "anchor-click", commentId: id });
          return;
        }
      }
    }
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);

  // Recompute located ranges and repaint highlights whenever the content or the
  // anchor set changes. Runs after layout so the DOM text is present.
  useLayoutEffect(() => {
    const root = rootRef.current;
    const api = highlightApi();
    rangesRef.current = new Map();
    if (!root || !api) return;

    const rest: Range[] = [];
    let active: Range | null = null;
    for (const a of anchors) {
      const r = locateQuote(root, a.quote, a.prefix, a.suffix);
      if (!r) continue;
      rangesRef.current.set(a.id, r);
      if (a.id === focusedId) active = r;
      else rest.push(r);
    }

    api.registry.set("pd-anchor", new api.Ctor(...rest) as never);
    if (active) {
      api.registry.set("pd-anchor-active", new api.Ctor(active) as never);
    } else {
      api.registry.delete("pd-anchor-active");
    }
  }, [payload, anchors, focusedId]);

  // Scroll the focused anchor into view when focus changes.
  useEffect(() => {
    if (!focusedId) return;
    const r = rangesRef.current.get(focusedId);
    const el =
      r?.startContainer.nodeType === Node.ELEMENT_NODE
        ? (r.startContainer as Element)
        : r?.startContainer.parentElement;
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focusedId, anchors, payload]);

  const reportHeight = useCallback(() => {
    const h = rootRef.current?.scrollHeight ?? document.body.scrollHeight;
    postToParent({ source: RENDERER_SOURCE, type: "height", height: h });
  }, []);

  useLayoutEffect(() => {
    reportHeight();
    const ro = new ResizeObserver(reportHeight);
    if (rootRef.current) ro.observe(rootRef.current);
    return () => ro.disconnect();
  }, [payload, reportHeight]);

  return (
    <div ref={rootRef} className="pd-root">
      {!payload ? (
        <div className="pd-empty">Waiting for content…</div>
      ) : (
        <Content payload={payload} onLoaded={reportHeight} />
      )}
    </div>
  );
}

function Content({ payload, onLoaded }: { payload: RenderPayload; onLoaded: () => void }) {
  if (payload.contentType === "markdown") {
    return (
      <article className="prose markdown-body">
        <MarkdownRenderer source={payload.sourceContent} />
      </article>
    );
  }

  if (payload.contentType === "safe_html") {
    const html = payload.renderedHtml ?? DOMPurify.sanitize(payload.sourceContent);
    return <article className="prose" dangerouslySetInnerHTML={{ __html: html }} />;
  }

  // sandbox_html: isolate untrusted markup in a script-disabled iframe.
  return <SandboxFrame html={payload.sourceContent} onResize={onLoaded} />;
}

// Untrusted HTML stays script-free (no allow-scripts), but allow-same-origin
// lets us read its real content height so the frame fits exactly — otherwise a
// fixed height leaves blank space under short reports or nested-scrolls long ones.
function SandboxFrame({ html, onResize }: { html: string; onResize: () => void }) {
  const ref = useRef<HTMLIFrameElement>(null);
  const roRef = useRef<ResizeObserver | null>(null);

  const sync = useCallback(() => {
    const frame = ref.current;
    const doc = frame?.contentDocument;
    if (!frame || !doc) return;
    const h = Math.max(
      doc.documentElement?.scrollHeight ?? 0,
      doc.body?.scrollHeight ?? 0,
    );
    if (h > 0) frame.style.height = `${h}px`;
    onResize();
  }, [onResize]);

  const onLoad = useCallback(() => {
    sync();
    const doc = ref.current?.contentDocument;
    roRef.current?.disconnect();
    if (doc?.body) {
      const ro = new ResizeObserver(sync);
      ro.observe(doc.body);
      roRef.current = ro;
      // Late reflows: images inside the report finishing loading.
      doc.querySelectorAll("img").forEach((img) => {
        if (!img.complete) img.addEventListener("load", sync);
      });
    }
  }, [sync]);

  useEffect(() => () => roRef.current?.disconnect(), []);

  return (
    <iframe
      ref={ref}
      className="pd-sandbox"
      sandbox="allow-same-origin"
      referrerPolicy="no-referrer"
      srcDoc={html}
      title="sandboxed content"
      onLoad={onLoad}
    />
  );
}
