#!/usr/bin/env python3
"""Build a single self-contained vidscope.py from the four source files.

Why: Agensi runs each script from an isolated temporary file, so the shipped
file cannot import vd_probe / vd_sheet / vd_brief as siblings. The public CLI
must survive the merge, so the dispatcher's probe/sheet/brief interface is
reproduced at the end of the merged file.

The only name collision across the modules is `main`, which is renamed per
module (main_probe / main_sheet / main_brief) before concatenation.

Output goes to dist/agensi/vidscope/scripts/vidscope.py
"""
import pathlib
import re

SRC = pathlib.Path.home() / "repos/vidscope/scripts"
OUT = pathlib.Path.home() / "repos/vidscope/dist/agensi/vidscope/scripts/vidscope.py"

MODULES = [
    ("vd_probe.py",  "main_probe",  "PROBE"),
    ("vd_sheet.py",  "main_sheet",  "SHEET"),
    ("vd_brief.py",  "main_brief",  "BRIEF"),
]

HEADER = '''#!/usr/bin/env python3
"""
vidscope — see inside any video without watching it.

  vidscope probe  VIDEO [--json]                technical forensics
  vidscope sheet  VIDEO --rung {1,2,3} [...]    contact sheets for vision
  vidscope brief  VIDEO [--target 21 34]        readable report + segment plan

Self-contained build: the probe, sheet and brief engines are inlined below
rather than imported, so this single file runs from an isolated temporary
directory with no sibling files. Requires only Python 3.8+ and ffmpeg/ffprobe
on PATH. No third-party packages, no network access.

MIT licensed. Source: https://github.com/pakundur/VIDSCOPE
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VERSION = "1.0.4"


# =====================================================================
# Shared helpers
# =====================================================================

def _run(cmd):
    """Run a command, returning CompletedProcess with text output."""
    return subprocess.run(cmd, capture_output=True, text=True)
'''

FOOTER = '''

# =====================================================================
# Dispatcher — public CLI
# =====================================================================

COMMANDS = {
    "probe": ("technical forensics: duration, cuts, black/freeze, luma, flags", main_probe),
    "sheet": ("contact sheets at rung 1 (330px) / 2 (760px) / 3 (1080px)", main_sheet),
    "brief": ("markdown brief + beat table + pre-filled vision prompt", main_brief),
}


def usage():
    print("vidscope — see inside any video without watching it\\n")
    print("usage: vidscope COMMAND [args...]\\n")
    print("commands:")
    for name, (desc, _) in COMMANDS.items():
        print(f"  {name:<8} {desc}")
    print("\\nexamples:")
    print("  vidscope probe clip.mp4")
    print("  vidscope probe clip.mp4 --json")
    print("  vidscope sheet clip.mp4 --rung 1")
    print("  vidscope sheet clip.mp4 --rung 3 --times 5.0 5.5 6.0")
    print("  vidscope brief clip.mp4 --target 21 34")
    print(f"\\nvidscope {VERSION} · MIT · requires ffmpeg on PATH")


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        usage()
        sys.exit(0)
    if argv[0] in ("-v", "--version", "version"):
        print(VERSION)
        sys.exit(0)

    cmd = argv[0]
    if cmd not in COMMANDS:
        print(f"vidscope: unknown command '{cmd}'\\n", file=sys.stderr)
        usage()
        sys.exit(2)

    fn = COMMANDS[cmd][1]

    # `brief` accepts either a video (probe it first) or a JSON payload, which
    # may be a file path or '-' for stdin. The -form preserves the original
    # vd_brief.py direct-call behaviour, where probe JSON is piped in.
    if cmd == "brief":
        args = argv[1:]
        if args and args[0] == "-":
            # JSON from stdin; run the brief engine directly.
            sys.argv = ["vidscope", *args]
            fn()
            return
        if args and not args[0].endswith(".json"):
            video = args[0]
            rest = args[1:]
            saved_argv = sys.argv
            try:
                sys.argv = ["vidscope", video, "--json"]
                import io
                from contextlib import redirect_stdout
                buf = io.StringIO()
                with redirect_stdout(buf):
                    try:
                        main_probe()
                    except SystemExit as e:
                        if e.code not in (0, None):
                            sys.exit(e.code)
                payload = buf.getvalue()
            finally:
                sys.argv = saved_argv
            sys.stdin = io.StringIO(payload)
            sys.argv = ["vidscope", "-", *rest]
            fn()
            return

    sys.argv = ["vidscope", *argv[1:]]
    fn()


if __name__ == "__main__":
    main()
'''


def strip_module(path, new_main):
    """Return module source with header removed, imports dropped, main renamed."""
    txt = path.read_text(encoding="utf-8")

    # drop shebang + module docstring
    txt = re.sub(r'\A#!.*?\n', '', txt)
    txt = re.sub(r'\A\s*""".*?"""\n', '', txt, flags=re.S)

    lines = []
    for ln in txt.split("\n"):
        s = ln.strip()
        # drop top-level stdlib imports; the merged header provides them
        if re.match(r'^(import|from)\s+(argparse|json|re|shutil|subprocess|sys|tempfile|io|pathlib)\b', s):
            continue
        # drop the module's own __main__ guard
        if s == 'if __name__ == "__main__":':
            break
        lines.append(ln)

    body = "\n".join(lines).strip("\n")
    body = re.sub(r'^def main\(\):', f'def {new_main}():', body, flags=re.M)
    return body


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    parts = [HEADER]
    for fname, newmain, label in MODULES:
        body = strip_module(SRC / fname, newmain)
        bar = "=" * 69
        parts.append(f"\n\n# {bar}\n# {label} engine (from {fname})\n# {bar}\n\n{body}")
    parts.append(FOOTER)

    merged = "\n".join(parts)
    OUT.write_text(merged, encoding="utf-8")
    OUT.chmod(0o755)
    size = OUT.stat().st_size
    print(f"wrote {OUT}")
    print(f"  {size:,} bytes ({size/1024:.1f} KB)")
    print(f"  lines: {merged.count(chr(10))}")
    # guideline is <20KB for easy review; report honestly
    print(f"  under 20KB guideline: {size < 20000}")


if __name__ == "__main__":
    main()
