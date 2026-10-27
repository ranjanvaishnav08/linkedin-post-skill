#!/usr/bin/env python3
"""clean.py - fix what is safe to fix, flag what needs a human.

Auto-fixed (meaning never changes):
  invisible/format characters, curly quotes, the single-character ellipsis,
  non-breaking and narrow spaces, doubled spaces.

Flagged, never rewritten (meaning can change):
  em and en dashes used as dashes, stock "AI" words and phrases, structural
  tells like "It's not just X, it's Y".

Usage:
  python3 clean.py draft.txt              # cleaned text to stdout, report to stderr
  python3 clean.py draft.txt -o out.txt
  python3 clean.py draft.txt --json       # machine-readable report on stdout
"""
import argparse
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
LEX = os.path.join(HERE, "slop.json")

SAFE_MAP = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
    "\u2026": "...",
    "\u00a0": " ", "\u202f": " ", "\u2007": " ", "\u2009": " ", "\u200a": " ",
}
URL_RE = re.compile(r"https?://\S+|www\.\S+|\S+@\S+\.\S+")


def load_lexicon(path=LEX):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _line_of(text, idx):
    return text.count("\n", 0, idx) + 1


def fix_safe(text):
    """Return (text, counts). Only substitutions that cannot change meaning."""
    counts = {}
    out = []
    for ch in text:
        cat = unicodedata.category(ch)
        if ch in SAFE_MAP:
            counts[f"U+{ord(ch):04X} {unicodedata.name(ch, '?')}"] = \
                counts.get(f"U+{ord(ch):04X} {unicodedata.name(ch, '?')}", 0) + 1
            out.append(SAFE_MAP[ch])
        elif cat == "Cf" or 0xE0000 <= ord(ch) <= 0xE007F:
            key = f"U+{ord(ch):04X} {unicodedata.name(ch, 'INVISIBLE')}"
            counts[key] = counts.get(key, 0) + 1
        else:
            out.append(ch)
    text = "".join(out)
    # Collapse runs of spaces inside lines only; never touch line breaks.
    text = re.sub(r"(?<=\S)[ \t]{2,}(?=\S)", " ", text)
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    return text, counts


def flag_dashes(text):
    flags = []
    for m in re.finditer(r"[\u2014\u2013]", text):
        ch = m.group(0)
        before = text[max(0, m.start() - 1)]
        after = text[m.end()] if m.end() < len(text) else ""
        if ch == "\u2013" and before.isdigit() and after.isdigit():
            continue  # 5-10 range: an en dash is correct, leave it
        name = "em dash" if ch == "\u2014" else "en dash used as a dash"
        snippet = text[max(0, m.start() - 30): m.end() + 30].replace("\n", " ")
        flags.append({"kind": name, "line": _line_of(text, m.start()),
                      "context": snippet.strip(),
                      "fix": "Rewrite: full stop, comma, colon or parentheses, "
                             "whichever the sentence actually needs."})
    return flags


def flag_lexicon(text, lex):
    flags = []
    masked = URL_RE.sub(lambda m: " " * len(m.group(0)), text)
    taken = []
    entries = sorted(lex["phrases"] + lex["words"], key=lambda e: len(e["find"]), reverse=True)
    for e in entries:
        pat = re.compile(r"\b" + re.escape(e["find"]).replace(r"\ ", r"\s+") + r"\b", re.I)
        for m in pat.finditer(masked):
            if any(a <= m.start() < b for a, b in taken):
                continue  # already inside a longer phrase hit
            taken.append((m.start(), m.end()))
            flags.append({"kind": "stock " + ("phrase" if " " in e["find"] else "word"),
                          "line": _line_of(text, m.start()), "found": m.group(0),
                          "suggest": e["replace"] or "(cut it)"})
    return sorted(flags, key=lambda f: f["line"])


def flag_structures(text, lex):
    flags = []
    for s in lex["structures"]:
        try:
            pat = re.compile(s["regex"], re.M)
        except re.error:
            continue
        for m in pat.finditer(text):
            flags.append({"kind": "structure", "line": _line_of(text, m.start()),
                          "name": s["name"], "fix": s["fix"]})
    return flags


def clean(text, lex=None):
    lex = lex or load_lexicon()
    text, fixed = fix_safe(text)
    flags = flag_dashes(text) + flag_lexicon(text, lex) + flag_structures(text, lex)
    return text, {"fixed": fixed, "flags": flags}


def render(report, out):
    fixed = report["fixed"]
    print(f"AUTO-FIXED: {sum(fixed.values())} characters", file=out)
    for k, n in fixed.items():
        print(f"  {n:>3} x {k}", file=out)
    print(f"\nFLAGGED FOR YOU TO REWRITE: {len(report['flags'])}", file=out)
    for f in report["flags"]:
        if f["kind"] == "structure":
            print(f"  L{f['line']}: {f['name']}. {f['fix']}", file=out)
        elif f["kind"].startswith("stock"):
            print(f"  L{f['line']}: \"{f['found']}\" -> consider \"{f['suggest']}\"", file=out)
        else:
            print(f"  L{f['line']}: {f['kind']} in \"...{f['context']}...\"", file=out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="file, or - for stdin")
    ap.add_argument("-o", "--out")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    raw = sys.stdin.read() if a.input == "-" else open(a.input, encoding="utf-8").read()
    text, report = clean(raw)
    if a.json:
        print(json.dumps({"text": text, **report}, indent=2))
        return
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
    render(report, sys.stderr)


if __name__ == "__main__":
    main()
