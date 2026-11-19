#!/usr/bin/env python3
"""Pre-flight check against Agensi's 8-point security scan.

Runs the same categories Agensi documents, on the package as it will be zipped.
This is not a guarantee of passing (Agensi does not publish its exact patterns),
but it catches the failures that are detectable from their published rules.
"""
import pathlib
import re
import sys

PKG = pathlib.Path.home() / "repos/vidscope/dist/agensi/vidscope"

# Agensi hard-fails on these
EXEC_EXTS = {".exe", ".dll", ".so", ".dylib", ".bin", ".app", ".dmg",
             ".msi", ".deb", ".rpm", ".wasm", ".class", ".jar", ".war"}

DANGEROUS = [
    (r"\bshell\s*=\s*True", "shell=True"),
    (r"\bos\.system\s*\(", "os.system()"),
    (r"chmod\s+777", "chmod 777"),
    (r"rm\s+-rf\s+/(?:\s|$)", "rm -rf /"),
    (r"curl[^\n|]*\|\s*(?:ba)?sh", "piping a download into a shell"),
    (r"wget[^\n|]*\|\s*(?:ba)?sh", "piping a download into a shell"),
    (r"eval\s*\(\s*(?:input|sys\.argv)", "eval of user input"),
]
SECRETS = [
    (r"(?i)\b(?:api[_-]?key|secret|password|passwd|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{12,}", "hardcoded credential"),
    (r"\bsk-[A-Za-z0-9]{20,}", "OpenAI-style key"),
    (r"\bghp_[A-Za-z0-9]{30,}", "GitHub token"),
    (r"AKIA[0-9A-Z]{16}", "AWS access key"),
]
INJECTION = [
    (r"(?i)ignore\s+(?:all\s+)?previous\s+instructions", "prompt injection"),
    (r"(?i)do\s+not\s+tell\s+the\s+user", "prompt injection"),
    (r"(?i)\bsecretly\b", "prompt injection"),
    (r"(?i)disregard\s+(?:the\s+)?(?:above|prior)", "prompt injection"),
]
OBFUSCATION = [
    (r"\bbase64\.b64decode\b", "base64 decode"),
    (r"\bexec\s*\(\s*base64", "encoded exec"),
    (r"\\x[0-9a-f]{2}\\x[0-9a-f]{2}\\x[0-9a-f]{2}", "hex-escaped payload"),
]
ENV = [
    (r"os\.environ\b", "reads env vars"),
    (r"os\.getenv\b", "reads env vars"),
]

results = []
def check(n, name, ok, detail=""):
    results.append((n, name, ok, detail))

files = sorted(p for p in PKG.rglob("*") if p.is_file()
               and "__pycache__" not in p.parts
               and p.suffix not in {".pyc", ".pyo"})
text_files = [p for p in files if p.suffix in {".md", ".py", ".txt", ".yaml", ".yml", ".json", ".sh"}]

# 1. file structure
has_skill = (PKG / "SKILL.md").is_file()
fm_ok = False
if has_skill:
    raw = (PKG / "SKILL.md").read_text(encoding="utf-8")
    if raw.startswith("---"):
        fm = raw.split("---")[1]
        try:
            import yaml
            d = yaml.safe_load(fm) or {}
            fm_ok = bool(d.get("name")) and bool(d.get("description"))
        except Exception:
            fm_ok = False
check(1, "File structure (SKILL.md + frontmatter)", has_skill and fm_ok,
      f"SKILL.md={has_skill} name+description={fm_ok}")

# 2. file types
bad_ext = [p for p in files if p.suffix.lower() in EXEC_EXTS]
check(2, "File types (no executables)", not bad_ext, str(bad_ext))

# 3-6 scan text
def scan(pats):
    hits = []
    for p in text_files:
        txt = p.read_text(encoding="utf-8", errors="ignore")
        for pat, label in pats:
            for m in re.finditer(pat, txt):
                line = txt[:m.start()].count("\n") + 1
                hits.append(f"{p.name}:{line} {label}")
    return hits

d_hits = scan(DANGEROUS)
check(3, "Dangerous command patterns", not d_hits, "; ".join(d_hits[:4]))
s_hits = scan(SECRETS)
check(4, "Secrets", not s_hits, "; ".join(s_hits[:4]))
e_hits = scan(ENV)
check(5, "Environment harvesting", not e_hits, "; ".join(e_hits[:4]))

# 6. network access
url_hits = []
for p in text_files:
    txt = p.read_text(encoding="utf-8", errors="ignore")
    for m in re.finditer(r"https?://[^\s\"'\)]+", txt):
        url_hits.append(f"{p.name}: {m.group(0)[:50]}")
net_imports = []
for p in text_files:
    txt = p.read_text(encoding="utf-8", errors="ignore")
    for mod in ("urllib", "requests", "socket", "httpx", "aiohttp", "http.client"):
        if re.search(rf"^\s*(?:import|from)\s+{re.escape(mod)}\b", txt, re.M):
            net_imports.append(f"{p.name}: {mod}")
check(6, "Network access", not url_hits and not net_imports,
      "; ".join((url_hits + net_imports)[:4]))

# 7. obfuscation
o_hits = scan(OBFUSCATION)
check(7, "Obfuscation", not o_hits, "; ".join(o_hits[:4]))

# 8. prompt injection
i_hits = scan(INJECTION)
check(8, "Prompt injection", not i_hits, "; ".join(i_hits[:4]))

# ---- report ----
print("Agensi pre-flight scan")
print(f"package: {PKG}")
print(f"files: {len(files)}  text: {len(text_files)}")
print("=" * 62)
fails = 0
for n, name, ok, detail in results:
    mark = "PASS" if ok else "FAIL"
    if not ok:
        fails += 1
    print(f"{mark}  {n}. {name}")
    if detail and not ok:
        print(f"       {detail}")
print("=" * 62)
print(f"{8 - fails}/8 passed")

sizes = sorted(((p.stat().st_size, p) for p in files), reverse=True)
print("\nlargest files:")
for s, p in sizes[:5]:
    rel = p.relative_to(PKG)
    note = "  <- over 20KB guideline" if s > 20000 and p.suffix == ".py" else ""
    print(f"  {s:7,} B  {rel}{note}")

sys.exit(1 if fails else 0)
