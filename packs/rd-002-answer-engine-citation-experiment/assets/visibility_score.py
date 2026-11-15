#!/usr/bin/env python3
"""Score an answer-engine citation experiment (pack rd-002).

Input CSV columns (one row per run):
  run_id, prompt_id, arm, engine, engine_version, run_date, answered, cited_urls, notes
    arm:        baseline | treatment   (or any label; scored separately)
    answered:   1 if the engine produced an answer, 0 if it refused/errored
    cited_urls: space-separated URLs shown as sources in that answer ('' if none)

Every rate is printed with its numerator AND denominator:
  runs_total                 all rows
  runs_answered              answered == 1
  runs_with_citations        answered and >=1 cited URL
  runs_citing_target         answered and >=1 cited URL on the target domain
  citation_rate              runs_citing_target / runs_with_citations
  answer_citation_rate       runs_citing_target / runs_answered
  prompt_coverage            prompts with >=1 run citing target / prompts in arm
  target_share_of_citations  target URLs cited / all URLs cited
95% Wilson intervals are given for the run-level rates. Small samples are directional.
"""
import argparse, csv, json, math, sys
from collections import defaultdict
from urllib.parse import urlparse


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0, c - h), 4), round(min(1, c + h), 4)]


def on_target(url, domain):
    host = (urlparse(url).hostname or "").lower()
    return host == domain or host.endswith("." + domain)


def score(rows, domain):
    out = {}
    groups = defaultdict(list)
    for r in rows:
        groups[(r["engine"], r["arm"])].append(r)
    for (engine, arm), rs in sorted(groups.items()):
        ans = [r for r in rs if r["answered"].strip() == "1"]
        withc = [r for r in ans if r["cited_urls"].split()]
        tgt = [r for r in withc if any(on_target(u, domain) for u in r["cited_urls"].split())]
        prompts = {r["prompt_id"] for r in rs}
        covered = {r["prompt_id"] for r in tgt}
        all_urls = [u for r in withc for u in r["cited_urls"].split()]
        t_urls = [u for u in all_urls if on_target(u, domain)]
        def rate(k, n):
            return {"num": k, "den": n, "rate": round(k / n, 4) if n else None, "ci95": wilson(k, n)}
        out[f"{engine}/{arm}"] = {
            "runs_total": len(rs), "runs_answered": len(ans), "runs_with_citations": len(withc),
            "runs_citing_target": len(tgt),
            "citation_rate": rate(len(tgt), len(withc)),
            "answer_citation_rate": rate(len(tgt), len(ans)),
            "prompt_coverage": {"num": len(covered), "den": len(prompts),
                                "rate": round(len(covered) / len(prompts), 4) if prompts else None},
            "target_share_of_citations": {"num": len(t_urls), "den": len(all_urls),
                                          "rate": round(len(t_urls) / len(all_urls), 4) if all_urls else None},
            "engine_versions": sorted({r["engine_version"] for r in rs}),
            "run_dates": sorted({r["run_date"] for r in rs}),
        }
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--domain", required=True, help="target domain, e.g. example.org")
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.csv, newline="")))
    print(json.dumps(score(rows, a.domain.lower()), indent=2))
