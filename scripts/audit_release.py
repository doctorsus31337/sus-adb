from __future__ import annotations

import codecs
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath


READ_SIZE = 64 * 1024
SNIFF_SIZE = 8 * 1024
PATTERN_OVERLAP = 512

BLOCKED_SUFFIXES = (
    ".pcap", ".pcapng", ".cap", ".apk", ".aab", ".apks", ".xapk",
    ".keystore", ".jks", ".p12", ".pfx", ".pem", ".key", ".db",
    ".db3", ".sqlite", ".sqlite3", ".log", ".crash", ".dmp", ".pyc",
    ".pyo",
)
BLOCKED_NAMES = {
    ".env", "credentials", "credentials.json", "secrets.json",
    "flutter_popup_bypass.js", "flutter_popup_bypass.meta.json",
}
BLOCKED_PARTS = {
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "cache",
    "caches", "cases", "evidence", "reports", "crash-reports", "plugin-state",
}
BINARY_SUFFIXES = {
    ".so", ".dll", ".pyd", ".exe", ".dylib", ".a", ".lib", ".o", ".obj",
    ".ttf", ".otf", ".woff", ".woff2", ".png", ".jpg", ".jpeg", ".gif",
    ".ico", ".bmp", ".webp", ".zip", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".whl", ".pdf",
}
TEXT_SUFFIXES = {
    ".txt", ".md", ".rst", ".json", ".toml", ".yaml", ".yml", ".ini",
    ".cfg", ".conf", ".xml", ".csv", ".tsv", ".py", ".pyw", ".js",
    ".ts", ".css", ".html", ".htm", ".sh", ".ps1", ".bat", ".cmd",
    ".spec", ".manifest", ".meta",
}
BINARY_MAGICS = (
    b"\x7fELF", b"MZ", b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe",
    b"PK\x03\x04", b"\x1f\x8b", b"BZh", b"\xfd7zXZ\x00", b"\x89PNG\r\n\x1a\n",
    b"GIF87a", b"GIF89a", b"\xff\xd8\xff", b"%PDF-",
)
PATTERNS = (
    ("developer-home", re.compile(r"(?:/home/[^/\s]+|C:\\Users\\[^\\\s]+)")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----")),
    ("token", re.compile(r"(?:ghp_|github_pat_|AKIA)[A-Za-z0-9_]{12,}")),
)
ALLOW = (
    "docs/privacy-security.md", "scripts/audit_release.py",
    "app/core/logging_manager.py", "app/core/crash_report.py",
    "tests/test_crash_report.py", "tests/test_logging_manager.py",
    "tests/test_release_manifest.py", "tests/test_release_audit.py",
)


def tracked(root="."):
    try:
        return subprocess.check_output(("git", "ls-files", "-z"), cwd=root).decode().split("\0")[:-1]
    except Exception:
        return [p.relative_to(root).as_posix() for p in Path(root).rglob("*") if p.is_file()]


def path_finding(relative):
    path = PurePosixPath(relative)
    lower = relative.casefold()
    parts = tuple(part.casefold() for part in path.parts)
    name = path.name.casefold()
    if lower.endswith(BLOCKED_SUFFIXES) or name in BLOCKED_NAMES:
        return "generated-artifact"
    if any(part in BLOCKED_PARTS for part in parts):
        return "generated-artifact"
    if len(parts) >= 2 and parts[0] == "plugins" and parts[1] != "examples":
        return "installed-plugin"
    if name.startswith(("private-", "private_", "draft-", "draft_")):
        return "private-draft"
    return None


def classify_file(path):
    suffix = path.suffix.casefold()
    try:
        with path.open("rb") as stream:
            sample = stream.read(SNIFF_SIZE)
    except OSError:
        return "unreadable"
    if suffix in BINARY_SUFFIXES or any(sample.startswith(magic) for magic in BINARY_MAGICS):
        return "binary"
    if b"\0" in sample:
        return "binary"
    try:
        sample.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return "malformed-text" if suffix in TEXT_SUFFIXES else "binary"
    return "text"


def scan_text(path):
    findings = []
    decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
    tail = ""
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(READ_SIZE):
                text = decoder.decode(chunk)
                searchable = tail + text
                for name, pattern in PATTERNS:
                    if name not in findings and pattern.search(searchable):
                        findings.append(name)
                tail = searchable[-PATTERN_OVERLAP:]
            decoder.decode(b"", final=True)
    except (OSError, UnicodeDecodeError):
        return ("malformed-text",)
    return tuple(findings)


def _audit_paths(base, relative_paths, allowed=()):
    findings = []
    for rel in sorted(relative_paths):
        if rel in allowed:
            continue
        path = base / rel
        rule = path_finding(rel)
        if rule:
            findings.append((rel, rule))
            continue
        classification = classify_file(path)
        if classification == "malformed-text":
            findings.append((rel, classification))
        elif classification == "text":
            findings.extend((rel, rule) for rule in scan_text(path))
    return tuple(findings)


def audit(root="."):
    return _audit_paths(Path(root), tracked(root), ALLOW)


def audit_tree(root):
    base = Path(root)
    relative_paths = (
        path.relative_to(base).as_posix()
        for path in base.rglob("*")
        if path.is_file()
    )
    return _audit_paths(base, relative_paths)


if __name__ == "__main__":
    found = audit_tree(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == "--tree" else audit()
    for path, kind in found:
        print(f"BLOCK {kind}: {path}")
    raise SystemExit(1 if found else 0)
