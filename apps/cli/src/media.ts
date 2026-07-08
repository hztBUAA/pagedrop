import { extname } from "node:path";

export const MIME_BY_EXT: Record<string, string> = {
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".gif": "image/gif",
};

export const EXT_BY_MIME: Record<string, string> = {
  "image/png": "png",
  "image/jpeg": "jpg",
  "image/webp": "webp",
  "image/gif": "gif",
};

const MD_IMAGE = /!\[[^\]]*\]\(\s*([^)\s]+)(?:\s+"[^"]*")?\s*\)/g;
const HTML_IMAGE = /<img\b[^>]*?\bsrc\s*=\s*["']([^"']+)["']/gi;

export function isLocalPath(p: string): boolean {
  if (!p) return false;
  return !/^(https?:|data:|pagedrop:|\/\/|#|mailto:)/i.test(p);
}

/** Unique local image paths referenced by Markdown or HTML content. */
export function extractLocalImageRefs(content: string): string[] {
  const found = new Set<string>();
  for (const re of [MD_IMAGE, HTML_IMAGE]) {
    re.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(content)) !== null) {
      const path = m[1];
      if (isLocalPath(path)) found.add(path);
    }
  }
  return [...found];
}

/** Asset ids referenced via pagedrop://asset/<id>. */
export function extractAssetIds(content: string): string[] {
  const re = /pagedrop:\/\/asset\/([0-9a-fA-F-]{8,})/g;
  const found = new Set<string>();
  let m: RegExpExecArray | null;
  while ((m = re.exec(content)) !== null) found.add(m[1]);
  return [...found];
}

/** Replace every occurrence of a raw path (used inside image refs) with a new value. */
export function replaceRef(content: string, from: string, to: string): string {
  return content.split(from).join(to);
}

export function mimeForPath(path: string): string | undefined {
  return MIME_BY_EXT[extname(path).toLowerCase()];
}
