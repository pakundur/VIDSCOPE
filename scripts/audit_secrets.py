#!/usr/bin/env python3
"""Scan the vidscope repo for leaked credentials and private information.

Covers tracked files, untracked-but-present files, and the full git history
(a secret removed in a later commit is still in the history and still leaked).

Read-only. Prints findings; writes nothing.
"""
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path.home() / "repos/vidscope"

PATTERNS = {
    "R2 access/account id":  r"\b[a-f0-9]{32}\b",
    "Cloudflare API token":  r"cfat_[A-Za-z0-9]{30,}",
    "AWS access key":        r"\bAKIA[0-9A-Z]{16}\b",
    "AWS secret":            r"(?i)aws_?secret[^\n]{0,50}",
    "OpenAI key":            r"\bsk-[A-Za-z0-9\-_]{20,}",
    "GitHub token":          r"\bgh[pousr]_[A-Za-z0-9]{30,}",
    "GitHub PAT fine":       r"\bgithub_pat_[A-Za-z0-9_]{30,}",
    "Anthropic key":         r"\bsk-ant-[A-Za-z0-9\-_]{20,}",
    "Google API key":        r"\bAIza[0-9A-Za-z\-_]{35}",
    "Slack token":           r"\bxox[abposr]-[A-Za-z0-9\-]{10,}",
    "Telegram bot token":    r"\b\d{8,10}:[A-Za-z0-9\-_]{35}",
    "private key block":     r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "secret assignment":     r"(?i)\b(api[_-]?key|secret|passwd|password|token|apikey)\s*[:=]\s*['\"][^'\"]{8,}['\"]",
    "R2 env names":          r"\bR2_(ACCESS_KEY|SECRET_KEY|ENDPOINT)\b",
    "CF env names":          r"\bCF_TOKEN\b|\bCF_ACCOUNT\b",
    "email address":         r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
    "phone number":          r"(?:\+?6?0?1\d[\-\s]?\d{3,4}[\-\s]?\d{3,4})",
    "local absolute path":   r"/(?:data/data/com\.termux|home/[a-z]{2,}|Users/[A-Za-z]{2,})/",
    "private r2.dev base":   r"pub-[a-f0-9]{32}\.r2\.dev",
    "r2 storage endpoint":   r"r2\.cloudflarestorage\.com",
    "personal domain":       r"(?i)\b(resepifesbuk|imika|pakundur\.github\.io|thesundaily|kliniksalam)\b",
}

# things that are fine and would otherwise trip a pattern
ALLOW = [
    (r"\bnoreply@github\.com\b", "github noreply"),
    (r"example\.com", "example domain"),
    (r"user@example", "example user"),
]


def sh(*args):
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True).stdout


def scan_text(label, text, fname):
    out = []
    for allow_pat, _ in ALLOW:
        text = re.sub(allow_pat, "ALLOWED", text)
    for name, pat in PATTERNS.items():
        for m in re.finditer(pat, text):
            line = text[:m.start()].count("\n") + 1
            out.append((name, fname, line, m.group(0)[:80]))
    return out


def main():
    tracked = sh("git", "ls-files").split()
    print(f"repo: {REPO}")
    print(f"tracked files: {len(tracked)}")
    print("=" * 74)

    findings = []

    # 1. tracked files
    for f in tracked:
        p = REPO / f
        if not p.exists():
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        findings += scan_text("tracked", txt, f)

    # 2. untracked / ignored files present on disk
    others = []
    for p in REPO.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(REPO))
        if rel in tracked or rel.startswith(".git/"):
            continue
        if p.suffix in {".png", ".jpg", ".pyc"}:
            continue
        others.append(rel)
    print(f"untracked-but-present files (non-binary): {len(others)}")
    for f in others:
        try:
            txt = (REPO / f).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        findings += scan_text("untracked", txt, f + "  [UNTRACKED]")

    # 3. full git history - a secret deleted later is still in history
    print("scanning git history (all commits, all blobs)...")
    hist = subprocess.run(
        ["git", "log", "-p", "--all", "--no-color"],
        cwd=REPO, capture_output=True, text=True, errors="ignore"
    ).stdout
    for name, pat in PATTERNS.items():
        for m in re.finditer(pat, hist):
            line = hist[:m.start()].count("\n") + 1
            findings.append((name, "GIT HISTORY", line, m.group(0)[:80]))

    # report
    print("=" * 74)
    if not findings:
        print("CLEAN: no credential or private-info patterns found")
        print("       (tracked files, untracked files, and full git history)")
        return 0

    by_cat = {}
    for name, f, line, val in findings:
        by_cat.setdefault(name, []).append((f, line, val))
    print(f"FINDINGS: {len(findings)} total across {len(by_cat)} categories\n")
    for name, items in sorted(by_cat.items()):
        print(f"[{name}]  {len(items)} hit(s)")
        seen = set()
        shown = 0
        for f, line, val in items:
            key = (f, val)
            if key in seen:
                continue
            seen.add(key)
            print(f"   {f}:{line}  {val}")
            shown += 1
            if shown >= 6:
                if len(items) > shown:
                    print(f"   ... {len(items)-shown} more")
                break
        print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
