"""Best-effort secret detection to stop agents/users from publishing credentials."""

import re
from dataclasses import dataclass

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("anthropic_api_key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("openai_api_key", re.compile(r"sk-[A-Za-z0-9_\-]{20,}")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("database_url", re.compile(r"(?:postgres|postgresql|mysql|mongodb)://[^\s:@/]+:[^\s:@/]+@")),
    ("bearer_token", re.compile(r"[Bb]earer\s+[A-Za-z0-9\-_.=]{20,}")),
    (
        "env_secret_assignment",
        re.compile(
            r"(?im)^\s*[A-Z0-9_]*(?:SECRET|TOKEN|API[_-]?KEY|PASSWORD|PASSWD|PRIVATE[_-]?KEY)"
            r"[A-Z0-9_]*\s*[=:]\s*['\"]?[^\s'\"]{6,}"
        ),
    ),
]


@dataclass
class Finding:
    type: str
    line: int
    preview: str

    def as_dict(self) -> dict:
        return {"type": self.type, "line": self.line, "preview": self.preview}


def _mask(matched: str) -> str:
    """Return a redacted preview that never reveals the full secret."""
    stripped = matched.strip()
    # Keep a small, non-sensitive prefix; mask the remainder.
    keep = min(6, max(2, len(stripped) // 4))
    head = stripped[:keep]
    return f"{head}{'*' * 4}"


def scan(content: str) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[tuple[str, int]] = set()
    lines = content.splitlines()
    for lineno, line in enumerate(lines, start=1):
        for kind, pattern in _PATTERNS:
            m = pattern.search(line)
            if m and (kind, lineno) not in seen:
                seen.add((kind, lineno))
                # Preview shows the key name context but masks the value.
                token = m.group(0)
                if kind == "env_secret_assignment":
                    key_part = re.split(r"[=:]", line, maxsplit=1)[0].strip()
                    preview = f"{key_part}={_mask(token.split('=')[-1].split(':')[-1])}"
                else:
                    preview = _mask(token)
                findings.append(Finding(type=kind, line=lineno, preview=preview))
    return findings
