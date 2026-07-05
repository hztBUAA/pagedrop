"""Server-side content safety and metadata extraction.

The React renderer performs the rich final rendering, but the backend still
sanitizes HTML (defence in depth) and derives preview metadata.
"""

import re

import nh3

from app.models.project import CONTENT_SAFE_HTML, CONTENT_SANDBOX_HTML

# Conservative allowlist: presentational tags only, no script/style/iframe/object.
_ALLOWED_TAGS = {
    "a", "abbr", "b", "blockquote", "br", "caption", "code", "col", "colgroup",
    "dd", "del", "details", "div", "dl", "dt", "em", "figcaption", "figure",
    "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img", "ins", "kbd", "li",
    "mark", "ol", "p", "pre", "q", "s", "samp", "small", "span", "strong",
    "sub", "summary", "sup", "table", "tbody", "td", "tfoot", "th", "thead",
    "tr", "u", "ul",
}
_ALLOWED_ATTRS = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title", "width", "height"},
    "*": {"class", "id"},
}


def sanitize_html(html: str) -> str:
    """Strip scripts, event handlers, javascript: URLs, and dangerous elements."""
    return nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        url_schemes={"http", "https", "mailto", "data"},
        link_rel="noopener noreferrer nofollow",
    )


def prepare_content(content_type: str, source: str) -> str | None:
    """Return sanitized HTML to store as rendered_html, or None to render client-side.

    - safe_html:    sanitized on the server and stored.
    - sandbox_html: stored raw; the frontend isolates it in a sandboxed iframe.
    - markdown:     rendered client-side by the React renderer.
    """
    if content_type == CONTENT_SAFE_HTML:
        return sanitize_html(source)
    if content_type == CONTENT_SANDBOX_HTML:
        return None
    return None


_MD_STRIP = re.compile(r"[#>*_`~\[\]()!\-]+")


def make_summary(content_type: str, source: str, limit: int = 200) -> str:
    text = source
    if content_type in (CONTENT_SAFE_HTML, CONTENT_SANDBOX_HTML):
        text = nh3.clean(source, tags=set())  # strip all tags -> text
    text = _MD_STRIP.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]
