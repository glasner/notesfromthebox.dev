#!/usr/bin/env python3
"""Check a claim/evidence ledger (pack rd-001).

Input: JSON Lines, one evidence row per line:
  {"claim_key", "claim", "value", "as_of", "source_url", "publisher", "source_kind",
   "source_date", "fetched", "quote", "scope"}
source_kind: primary | secondary | community.  Dates: YYYY-MM-DD; source_date may be null.

Output: one verdict per claim_key:
  SUPPORTED      >=1 primary source, no conflicting values within the same scope
  CONTRADICTED   two sources in the same scope disagree on value
  SCOPE-SPLIT    sources disagree but carry different scopes (both may be true)
  SECONDARY-ONLY no primary source
  STALE          newest source_date older than --max-age-days before --as-of
  UNDATED        no source carries a source_date
  INCOMPLETE     a row lacks url, fetched date, or quote
A claim can carry several flags. Exit 1 if any claim is CONTRADICTED or INCOMPLETE.
"""
import argparse, datetime, json, sys
from collections import defaultdict


def d(s):
    return datetime.date.fromisoformat(s) if s else None


def check(rows, as_of, max_age):
    by = defaultdict(list)
    for r in rows:
        by[r["claim_key"]].append(r)
    report = {}
    for key, rs in sorted(by.items()):
        flags = []
        if any(not r.get("source_url") or not r.get("fetched") or not r.get("quote") for r in rs):
            flags.append("INCOMPLETE")
        if not any(r.get("source_kind") == "primary" for r in rs):
            flags.append("SECONDARY-ONLY")
        dates = [d(r.get("source_date")) for r in rs if r.get("source_date")]
        if not dates:
            flags.append("UNDATED")
        elif (as_of - max(dates)).days > max_age:
            flags.append("STALE")
        scopes = defaultdict(set)
        for r in rs:
            scopes[r.get("scope") or "*"].add(str(r.get("value")).strip().lower())
        if any(len(v) > 1 for v in scopes.values()):
            flags.append("CONTRADICTED")
        elif len({next(iter(v)) for v in scopes.values()}) > 1:
            flags.append("SCOPE-SPLIT")
        if not flags or flags == ["SCOPE-SPLIT"]:
            flags.insert(0, "SUPPORTED")
        report[key] = {"flags": flags, "sources": len(rs),
                       "newest_source_date": max(dates).isoformat() if dates else None}
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger")
    ap.add_argument("--as-of", default=datetime.date.today().isoformat())
    ap.add_argument("--max-age-days", type=int, default=365)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(a.ledger) if l.strip()]
    rep = check(rows, d(a.as_of), a.max_age_days)
    if a.json:
        print(json.dumps(rep, indent=2))
    else:
        for k, v in rep.items():
            print(f"{k}: {' '.join(v['flags'])} (sources={v['sources']}, newest={v['newest_source_date']})")
    sys.exit(1 if any(f in v["flags"] for v in rep.values() for f in ("CONTRADICTED", "INCOMPLETE")) else 0)
