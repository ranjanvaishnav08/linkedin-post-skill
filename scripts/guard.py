#!/usr/bin/env python3
"""guard.py - confidentiality gate. Run it on every draft before showing it.

Catches the things that get employees and contractors in trouble: employer or
client names next to numbers, internal codenames, ticket IDs, internal URLs,
and language that signals non-public information.

It is a tripwire, not legal review. A clean result means none of these
patterns fired, not that the post is approved to publish.

Terms file (optional, recommended): one term per line, # for comments.
  Acme Bank
  Globex Consulting
  Project Falcon
Lines may start with "client:", "employer:" or "codename:" for nicer reports.

Usage:
  python3 guard.py draft.txt --terms guard.txt
  python3 guard.py draft.txt --terms guard.txt --json
Exit code: 0 clean, 1 warnings only, 2 at least one BLOCK.
"""
import argparse
import json
import re
import sys

SENT_RE = re.compile(r"[^.!?\n]+[.!?]*")
METRIC_RE = re.compile(
    r"(?:[$\u00a3\u20ac]\s?\d[\d,.]*\s?(?:[kmb]|million|billion|thousand)?"
    r"|\d[\d,.]*\s?(?:%|percent|bps|basis points|x\b)"
    r"|\b\d{1,3}(?:,\d{3})+\b"
    r"|\b\d+(?:\.\d+)?\s?(?:million|billion|mm|k)\b)", re.I)

BLOCK_PATTERNS = [
    (r"\b[A-Z][A-Z0-9]{1,9}-\d{1,6}\b", "ticket or issue ID"),
    (r"\b[\w.-]+\.(?:corp|internal|intranet|local)\b", "internal hostname"),
    (r"(?i)\b(?:confluence|jira|sharepoint|servicenow)\.[\w.-]+", "internal tool URL"),
    (r"(?i)slack\.com/archives", "Slack message link"),
    (r"\b\d{3}-\d{2}-\d{4}\b", "SSN-shaped number"),
    (r"\b(?:\d[ -]?){15,16}\b", "card-shaped number"),
    (r"(?i)\b(?:confidential|proprietary|under nda|not (?:yet )?public|internal only|"
     r"do not share|embargoed)\b", "says outright it is not public"),
]
WARN_PATTERNS = [
    (r"(?i)\b(?:unreleased|upcoming launch|pilot|beta|codename|code name|roadmap|"
     r"next quarter|q[1-4] (?:results|numbers|targets)|headcount|layoffs?|reorg|"
     r"restructur\w+|acquisition|merger|our (?:customers|clients) (?:data|accounts))\b",
     "may describe non-public plans or data"),
    (r"\b[\w.+-]+@[\w-]+\.[\w.]+\b", "email address"),
    (r"(?i)\b(?:at work|my team|our team|we) (?:shipped|launched|built|migrated|cut|saved|"
     r"grew|reduced|increased)\b", "work outcome: check it is public or approved"),
]
COMMON_CAPS = set("""AI ML API SQL PM TPM CEO CTO CFO COO VP SVP KPI OKR ROI USA US UK EU
NYC B2B B2C SAAS ETL ELT AWS GCP CRM ERP UX UI QA HR PR FAQ PDF CSV JSON
LLM GPT MBA PHD OK IPO LOL DM DMS ASAP FYI TL DR TLDR SEO MVP SDK CLI IDE GTM CX
I II III IV ET PT EST PST AM PM""".split())


def load_terms(path):
    terms = []
    if not path:
        return terms
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        kind = "term"
        m = re.match(r"(?i)(client|employer|codename|team|product)\s*:\s*(.+)", line)
        if m:
            kind, line = m.group(1).lower(), m.group(2).strip()
        terms.append((kind, line))
    return terms


def _line(text, i):
    return text.count("\n", 0, i) + 1


def check(text, terms):
    hits = []
    for pat, why in BLOCK_PATTERNS:
        for m in re.finditer(pat, text):
            hits.append({"level": "BLOCK", "line": _line(text, m.start()),
                         "found": m.group(0), "why": why})
    for pat, why in WARN_PATTERNS:
        for m in re.finditer(pat, text):
            hits.append({"level": "WARN", "line": _line(text, m.start()),
                         "found": m.group(0), "why": why})

    # Named terms: a mention is a warning; a mention plus a metric in the same
    # sentence is a block, because that is how internal numbers leak.
    for s in SENT_RE.finditer(text):
        sent = s.group(0)
        for kind, term in terms:
            if re.search(r"(?i)\b" + re.escape(term) + r"\b", sent):
                metric = METRIC_RE.search(sent)
                if metric:
                    hits.append({"level": "BLOCK", "line": _line(text, s.start()),
                                 "found": f"{term} + {metric.group(0).strip()}",
                                 "why": f"{kind} named next to a number"})
                else:
                    hits.append({"level": "WARN", "line": _line(text, s.start()),
                                 "found": term, "why": f"{kind} named"})

    # All-caps tokens that are not everyday acronyms often turn out to be codenames.
    for m in re.finditer(r"\b[A-Z]{3,12}\b", text):
        if m.group(0) not in COMMON_CAPS:
            hits.append({"level": "WARN", "line": _line(text, m.start()),
                         "found": m.group(0), "why": "unfamiliar acronym: codename?"})

    seen, out = set(), []
    for h in sorted(hits, key=lambda h: (h["level"] != "BLOCK", h["line"])):
        k = (h["level"], h["line"], h["found"].lower())
        if k not in seen:
            seen.add(k)
            out.append(h)
    blocks = sum(h["level"] == "BLOCK" for h in out)
    status = "BLOCK" if blocks else "WARN" if out else "CLEAR"
    return {"status": status, "blocks": blocks, "warnings": len(out) - blocks,
            "hits": out, "terms_checked": len(terms)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--terms")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    res = check(open(a.draft, encoding="utf-8").read(), load_terms(a.terms))
    if a.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"CONFIDENTIALITY: {res['status']}  "
              f"({res['blocks']} block, {res['warnings']} warn, "
              f"{res['terms_checked']} named terms checked)")
        if not res["terms_checked"]:
            print("  No terms file: employer and client names were NOT checked.")
        for h in res["hits"]:
            print(f"  {h['level']:<5} L{h['line']}: {h['found']!r}  ({h['why']})")
    sys.exit(2 if res["status"] == "BLOCK" else 1 if res["status"] == "WARN" else 0)


if __name__ == "__main__":
    main()
