/**
 * TextQuoteSelector-style anchoring over the rendered DOM.
 *
 * Whitespace is collapsed to single spaces so that a quote captured from the
 * rendered text can be relocated even if incidental whitespace differs. Matching
 * is exact within a version; across versions a moved/edited quote simply fails to
 * locate (returns null) rather than mis-highlighting.
 */

const CTX = 32; // chars of surrounding context stored as prefix/suffix

export interface AnchorSelection {
  quote: string;
  prefix: string;
  suffix: string;
}

function norm(s: string): string {
  return s.replace(/\s+/g, " ");
}

function commonSuffixLen(a: string, b: string): number {
  let n = 0;
  while (n < a.length && n < b.length && a[a.length - 1 - n] === b[b.length - 1 - n]) n++;
  return n;
}

function commonPrefixLen(a: string, b: string): number {
  let n = 0;
  while (n < a.length && n < b.length && a[n] === b[n]) n++;
  return n;
}

/** Build the current selection into a quote + surrounding context, or null. */
export function selectionToAnchor(root: HTMLElement, sel: Selection): AnchorSelection | null {
  if (sel.rangeCount === 0 || sel.isCollapsed) return null;
  const range = sel.getRangeAt(0);
  if (!root.contains(range.commonAncestorContainer)) return null;

  const quote = norm(range.toString()).trim();
  if (!quote) return null;

  const pre = document.createRange();
  pre.setStart(root, 0);
  pre.setEnd(range.startContainer, range.startOffset);
  const prefix = norm(pre.toString()).slice(-CTX);

  const post = document.createRange();
  post.setStart(range.endContainer, range.endOffset);
  post.setEnd(root, root.childNodes.length);
  const suffix = norm(post.toString()).slice(0, CTX);

  return { quote, prefix, suffix };
}

interface CharPos {
  node: Text;
  start: number;
  end: number;
}

interface TextIndex {
  text: string;
  chars: CharPos[];
}

function buildTextIndex(root: HTMLElement): TextIndex {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let text = "";
  const chars: CharPos[] = [];
  let prevWasSpace = false;
  let node = walker.nextNode() as Text | null;
  while (node) {
    const raw = node.data;
    for (let i = 0; i < raw.length; i++) {
      const isSpace = /\s/.test(raw[i]);
      if (isSpace) {
        if (prevWasSpace) continue; // collapse runs
        text += " ";
        prevWasSpace = true;
      } else {
        text += raw[i];
        prevWasSpace = false;
      }
      chars.push({ node, start: i, end: i + 1 });
    }
    node = walker.nextNode() as Text | null;
  }
  return { text, chars };
}

/** Locate a stored anchor in the rendered DOM, disambiguating by prefix/suffix. */
export function locateQuote(
  root: HTMLElement,
  quote: string,
  prefix: string,
  suffix: string,
): Range | null {
  const q = norm(quote).trim();
  if (!q) return null;
  const { text, chars } = buildTextIndex(root);

  const positions: number[] = [];
  let from = 0;
  for (;;) {
    const idx = text.indexOf(q, from);
    if (idx === -1) break;
    positions.push(idx);
    from = idx + 1;
  }
  if (positions.length === 0) return null;

  let best = positions[0];
  if (positions.length > 1) {
    const p = norm(prefix || "");
    const s = norm(suffix || "");
    let bestScore = -1;
    for (const idx of positions) {
      const before = text.slice(Math.max(0, idx - p.length), idx);
      const after = text.slice(idx + q.length, idx + q.length + s.length);
      const score = commonSuffixLen(before, p) + commonPrefixLen(after, s);
      if (score > bestScore) {
        bestScore = score;
        best = idx;
      }
    }
  }

  const startPos = chars[best];
  const endPos = chars[best + q.length - 1];
  if (!startPos || !endPos) return null;

  const range = document.createRange();
  range.setStart(startPos.node, startPos.start);
  range.setEnd(endPos.node, endPos.end);
  return range;
}
