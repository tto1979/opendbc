#!/usr/bin/env python3
"""
TOP: run the strict safety mutation test (mutation.py) and fail only on mutants that survive on lines TOP changed.

Upstream's own safety code is mutation tested upstream; the opendbc that openpilot v0.11.1 pins still has a few
survivors of its own, which are reported here but don't fail the run.

usage: GIT_REF=<upstream commit TOP's changes are diffed against> mutation_top.py [mutation.py args]
"""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SAFETY_PATHS = ["opendbc/safety/*.h", "opendbc/safety/modes/*.h"]
SURVIVOR_RE = re.compile(r"^- #\d+ (opendbc/safety/\S+?):(\d+)\b")
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def top_changed_lines(base: str) -> set[tuple[str, int]]:
  diff = subprocess.check_output(["git", "diff", "-U0", base, "HEAD", "--", *SAFETY_PATHS], cwd=ROOT, text=True)
  lines: set[tuple[str, int]] = set()
  path = None
  for line in diff.splitlines():
    if line.startswith("+++ "):
      path = line[len("+++ b/"):] if line != "+++ /dev/null" else None
    elif path is not None and (m := HUNK_RE.match(line)):
      start, count = int(m.group(1)), int(m.group(2) or 1)
      lines.update((path, n) for n in range(start, start + count))
  return lines


def main() -> int:
  base = os.environ.get("GIT_REF", "")
  if not base:
    print("mutation_top.py: set GIT_REF to the upstream commit to diff against", file=sys.stderr)
    return 2
  top_lines = top_changed_lines(base)
  print(f"TOP changed {len(top_lines)} safety lines since {base}", flush=True)

  survivors = []
  proc = subprocess.Popen([sys.executable, str(Path(__file__).with_name("mutation.py")), *sys.argv[1:]], cwd=ROOT,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
  assert proc.stdout is not None
  for line in proc.stdout:
    print(line, end="", flush=True)
    if m := SURVIVOR_RE.match(line):
      survivors.append((m.group(1), int(m.group(2)), line.strip()))
  ret = proc.wait()
  if ret not in (0, 1):
    return ret  # infra error, or the mutation library didn't build

  top_survivors = [s for s in survivors if (s[0], s[1]) in top_lines]
  upstream_survivors = [s for s in survivors if (s[0], s[1]) not in top_lines]
  print()
  if upstream_survivors:
    print(f"{len(upstream_survivors)} survivor(s) in upstream's code (mutation tested upstream, not failing):")
    for s in upstream_survivors:
      print(f"  {s[2]}")
  if top_survivors:
    print(f"{len(top_survivors)} survivor(s) on lines TOP changed:")
    for s in top_survivors:
      print(f"  {s[2]}")
    return 1
  print("no survivors on lines TOP changed")
  return 0


if __name__ == "__main__":
  sys.exit(main())
