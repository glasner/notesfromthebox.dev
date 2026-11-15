#!/usr/bin/env python3
"""Lint a coding-agent handoff brief (pack ab-001).

Checks that the brief:
  - has every required section
  - pins the base to a full commit SHA
  - lists at least one acceptance check with a runnable command and an expected result
  - states, in the Permissions section, that merge, push to the default branch and
    deploy are NOT granted, and grants nothing beyond the listed allowances
  - has stop conditions
Exit code 0 = pass, 1 = problems found (printed one per line).
"""
import re, sys

REQUIRED = ["Goal", "Base", "Scope", "Acceptance checks", "Permissions", "Stop conditions", "Report back"]
MUST_DENY = {"merge": r"\bmerge\b", "push to default branch": r"push\b.*\b(main|master|default branch)", "deploy": r"\bdeploy"}
GRANT_RED_FLAGS = [r"\bmay merge\b", r"\bcan merge\b", r"\bfeel free to (merge|deploy|push)", r"\bmay deploy\b", r"\bmay push to (main|master)"]


def sections(text):
    out, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            cur = m.group(1).strip()
            out[cur] = []
        elif cur:
            out[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def lint(text):
    problems = []
    s = sections(text)
    for r in REQUIRED:
        if r not in s or not s[r]:
            problems.append(f"missing or empty section: {r}")
    base = s.get("Base", "")
    if not re.search(r"\b[0-9a-f]{40}\b", base):
        problems.append("Base must pin a full 40-character commit SHA")
    checks = s.get("Acceptance checks", "")
    items = [l for l in checks.splitlines() if re.match(r"^\s*[-*\d]", l)]
    with_cmd = [l for l in items if "`" in l and re.search(r"expect", l, re.I)]
    if not with_cmd:
        problems.append("Acceptance checks need at least one item with a `command` and an 'expect' result")
    perms = s.get("Permissions", "")
    not_block = "\n".join(l for l in perms.splitlines() if re.search(r"\bnot\b|\bnever\b|\bno\b", l, re.I))
    for label, pat in MUST_DENY.items():
        if not re.search(pat, not_block, re.I):
            problems.append(f"Permissions must explicitly withhold: {label}")
    for pat in GRANT_RED_FLAGS:
        if re.search(pat, text, re.I):
            problems.append(f"brief appears to grant a landing/deploy permission: /{pat}/")
    return problems


if __name__ == "__main__":
    text = open(sys.argv[1]).read()
    probs = lint(text)
    for p in probs:
        print(p)
    sys.exit(1 if probs else 0)
