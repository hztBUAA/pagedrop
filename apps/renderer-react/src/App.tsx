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
  return (
    <iframe
      className="pd-sandbox"
      sandbox=""
      referrerPolicy="no-referrer"
      srcDoc={payload.sourceContent}
      title="sandboxed content"
      onLoad={onLoaded}
    />
  );
}
