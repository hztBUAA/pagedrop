import type { ComponentPropsWithoutRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeHighlight from "rehype-highlight";
import rehypeSanitize from "rehype-sanitize";
import { sanitizeSchema } from "./sanitizeSchema";
import { Mermaid } from "./Mermaid";

type CodeProps = ComponentPropsWithoutRef<"code"> & { inline?: boolean };

function Code({ inline, className, children, ...props }: CodeProps) {
  const match = /language-(\w+)/.exec(className ?? "");
  const lang = match?.[1];
  if (!inline && lang === "mermaid") {
    return <Mermaid chart={String(children).replace(/\n$/, "")} />;
  }
  return (
    <code className={className} {...props}>
      {children}
    </code>
  );
}

export function MarkdownRenderer({ source }: { source: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[
        rehypeKatex,
        [rehypeHighlight, { detect: true, ignoreMissing: true }],
        [rehypeSanitize, sanitizeSchema],
      ]}
      components={{ code: Code }}
    >
      {source}
    </ReactMarkdown>
  );
}
