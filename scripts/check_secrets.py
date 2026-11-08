"""Small portfolio guard for common credential formats; not a comprehensive secret scanner."""

import re
from pathlib import Path

PATTERNS = [
    re.compile(pattern)
    for pattern in [
        r"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}",
        r"gh[pousr]_[A-Za-z0-9]{36,}",
        r"AKIA[A-Z0-9]{16}",
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    ]
]
EXCLUDED = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    ".next",
    "test-results",
    "playwright-report",
}


def scan(root: Path) -> list[str]:
    findings = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or path.is_symlink() or any(p in EXCLUDED for p in relative.parts):
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            continue
        if relative.parts[:2] == ("evaluation", "results") or path.stat().st_size > 2_000_000:
            continue
        try:
            lines = path.read_text().splitlines()
        except (UnicodeError, OSError):
            continue
        for number, line in enumerate(lines, 1):
            if any(pattern.search(line) for pattern in PATTERNS):
                findings.append(f"{relative}:{number}")  # Never print matched credentials.
    return findings


if __name__ == "__main__":
    results = scan(Path(__file__).resolve().parents[1])
    if results:
        print("Possible secret formats in: " + ", ".join(results))
        raise SystemExit(1)
    print("Common secret-format guard passed; this is not a complete secret audit.")
