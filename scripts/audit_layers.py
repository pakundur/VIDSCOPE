#!/usr/bin/env python3
"""Report findings split by layer: working tree (fixable) vs git history (permanent).

The working tree is what a visitor to the repo sees today. Git history is every
version ever committed, still fetchable by anyone via `git log -p`. A string
removed in a later commit is still leaked in history.
"""
import pathlib
import re
import subprocess

REPO = pathlib.Path.home() / "repos/vidscope"

# Only the patterns that represent real infrastructure or personal info.
# Deliberately narrow: variable NAMES like R2_ACCESS_KEY are not secrets.
CHECKS = {
    "R2 public base":   r"pub-[a-f0-9]{32}\.r2\.dev",
    "R2 account id":    r"\b809f8446bb6155614855c191f9e09cfd\b|\b916db35501284776893235d4b8b6b758\b",
    "bucket name":      r"\bresepifesbuk(?:-videos)?\b",
    "work email":       r"saiful@thesundaily\.com",
    "local termux path": r"/data/data/com\.termux/files/home",
    "personal domain":  r"\b(?:imika\.my|kliniksalam|pakundur\.github\.io)\b",
}


def tree_hits():
    out = {}
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO,
                             capture_output=True, text=True).stdout.split()
    for name, pat in CHECKS.items():
        hits = []
        for f in tracked:
            if f == "scripts/audit_secrets.py":
                continue  # the scanner's own pattern list
            p = REPO / f
            if not p.exists() or p.suffix in {".png", ".jpg"}:
                continue
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for m in re.finditer(pat, txt):
                line = txt[:m.start()].count("\n") + 1
                hits.append(f"{f}:{line}")
        out[name] = hits
    return out


def history_hits():
    out = {}
    log = subprocess.run(["git", "log", "-p", "--all", "--no-color"],
                         cwd=REPO, capture_output=True, text=True,
                         errors="ignore").stdout
    # author/committer metadata too
    meta = subprocess.run(["git", "log", "--all", "--format=%ae%n%ce"],
                          cwd=REPO, capture_output=True, text=True).stdout
    blob = log + "\n" + meta
    for name, pat in CHECKS.items():
        n = len(re.findall(pat, blob))
        out[name] = n
    return out


t = tree_hits()
h = history_hits()

print("=" * 70)
print("WORKING TREE  (what the repo shows today)")
print("=" * 70)
tree_clean = True
for k, v in t.items():
    if v:
        tree_clean = False
        print(f"  LEAK  {k}: {v}")
    else:
        print(f"  ok    {k}")
print(f"\n  -> {'CLEAN' if tree_clean else 'STILL LEAKING'}")

print()
print("=" * 70)
print("GIT HISTORY  (every past commit, still fetchable)")
print("=" * 70)
hist_clean = True
for k, v in h.items():
    if v:
        hist_clean = False
        print(f"  EXPOSED  {k}: {v} occurrence(s)")
    else:
        print(f"  ok       {k}")
print(f"\n  -> {'CLEAN' if hist_clean else 'EXPOSED IN HISTORY'}")
