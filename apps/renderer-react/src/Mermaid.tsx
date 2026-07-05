import { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";

mermaid.initialize({
  startOnLoad: false,
  securityLevel: "strict",
  theme: "dark",
});

let counter = 0;

export function Mermaid({ chart }: { chart: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string>("");
  const [svg, setSvg] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    const id = `mermaid-${counter++}`;
    mermaid
      .render(id, chart)
      .then(({ svg }) => {
        if (!cancelled) setSvg(svg);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "diagram error");
      });
    return () => {
      cancelled = true;
    };
  }, [chart]);

  if (error) {
    return (
      <pre className="mermaid-error">
        Diagram error: {error}
        {"\n\n"}
        {chart}
      </pre>
    );
  }
  return <div ref={ref} className="mermaid" dangerouslySetInnerHTML={{ __html: svg }} />;
}
