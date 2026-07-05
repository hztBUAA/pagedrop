import { defaultSchema } from "rehype-sanitize";

// Extend the default sanitize schema to permit KaTeX and highlight.js output
// (class names on spans/code) while still stripping scripts and event handlers.
const base = defaultSchema;
const baseAttrs = base.attributes ?? {};

const katexTags = [
  "math",
  "semantics",
  "mrow",
  "mi",
  "mo",
  "mn",
  "msup",
  "msub",
  "mfrac",
  "annotation",
  "svg",
  "path",
  "line",
];

export const sanitizeSchema = {
  ...base,
  tagNames: [...(base.tagNames ?? []), ...katexTags],
  attributes: {
    ...baseAttrs,
    "*": [...(baseAttrs["*"] ?? []), "className", "style"],
    span: [...(baseAttrs.span ?? []), "className", "style", "ariaHidden"],
    code: [...(baseAttrs.code ?? []), "className"],
    svg: ["className", "width", "height", "viewBox", "preserveAspectRatio", "xmlns", "style"],
    path: ["d", "className"],
    annotation: ["encoding"],
  },
};
