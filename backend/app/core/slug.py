import re
import secrets

_slug_re = re.compile(r"[^a-z0-9]+")


def slugify(value: str, fallback: str = "workspace") -> str:
    value = (value or "").strip().lower()
    slug = _slug_re.sub("-", value).strip("-")
    if not slug:
        slug = fallback
    return slug[:100]


def random_suffix(n: int = 6) -> str:
    return secrets.token_hex(n // 2 + 1)[:n]
