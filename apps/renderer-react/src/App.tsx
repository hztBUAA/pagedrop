import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import DOMPurify from "dompurify";
import { MarkdownRenderer } from "./MarkdownRenderer";
import {
  isRenderMessage,
  RENDERER_SOURCE,
  type HeightMessage,
  type ReadyMessage,
  type RenderPayload,
} from "./protocol";

function postToParent(msg: ReadyMessage | HeightMessage) {
  if (window.parent && window.parent !== window) {
    window.parent.postMessage(msg, "*");
  }
}

export default function App() {
  const [payload, setPayload] = useState<RenderPayload | null>(
    (window as unknown as { __PAGEDROP_PAYLOAD__?: RenderPayload }).__PAGEDROP_PAYLOAD__ ?? null,
  );
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onMessage(e: MessageEvent) {
      if (isRenderMessage(e.data)) {
        setPayload(e.data.payload);
      }
    }
    window.addEventListener("message", onMessage);
    postToParent({ source: RENDERER_SOURCE, type: "ready" });
    return () => window.removeEventListener("message", onMessage);
  }, []);

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
