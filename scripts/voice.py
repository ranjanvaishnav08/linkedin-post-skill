#!/usr/bin/env python3
"""voice.py - does this draft sound like the person whose name goes on it?

Builds a style profile from the user's own past posts, then scores a draft
against it feature by feature. It does not ask "does this look human"; it asks
"does this look like *them*".

Past posts file: plain text, posts separated by a line containing only ---

Usage:
  python3 voice.py build past_posts.txt -o voice_profile.json
  python3 voice.py score draft.txt --profile voice_profile.json
  python3 voice.py score draft.txt --posts past_posts.txt     # build on the fly
  add --json to score for machine-readable output
"""
import argparse
import json
import math
import re
import statistics
import sys
from collections import Counter

SENT_RE = re.compile(r"[^.!?\n]+[.!?]*")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\u2019-]*")
CONTRACTION_RE = re.compile(r"\b\w+'(?:s|t|re|ve|ll|d|m)\b", re.I)
NUM_RE = re.compile(r"[$\u00a3\u20ac]?\d[\d,.]*%?[kKmMxX]?|\b(?:one|two|three|four|five|six|"
                    r"seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|"
                    r"hundred|thousand|million|billion|half|dozen)\b", re.I)
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27bf]")

# (key, label, plain-English hint when the draft drifts high / low)
FEATURES = [
    ("sent_len", "sentence length", "shorter sentences", "longer sentences"),
    ("sent_sd", "sentence variety", "more even rhythm", "mix short and long sentences"),
    ("para_sents", "paragraph size", "shorter paragraphs", "fewer one-line paragraphs"),
    ("words", "post length", "cut it down", "it can run longer"),
    ("contractions", "contractions", "fewer contractions", "use contractions (it's, don't)"),
    ("i_rate", "first person (I/me/my)", "less 'I'", "more first person"),
    ("we_rate", "we/our", "less 'we'", "more 'we'"),
    ("you_rate", "you/your", "less 'you'", "talk to the reader more"),
    ("numbers", "numbers per 100 words", "fewer numbers", "add a concrete number"),
    ("questions", "questions", "fewer questions", "they ask more questions"),
    ("exclaims", "exclamation marks", "drop the exclamation marks", "they use more energy"),
    ("emoji", "emoji", "drop the emoji", "they use emoji"),
    ("dashes", "dashes", "fewer dashes", "they use dashes"),
    ("long_words", "long words (9+ letters)", "plainer words", "they use more technical words"),
    ("hook_len", "line-1 length", "shorter first line", "longer first line"),
]
# Minimum spread so 3 near-identical samples do not make every draft fail.
SD_FLOOR = {"sent_len": 2.0, "sent_sd": 1.5, "para_sents": 0.4, "words": 40,
            "contractions": 1.0, "i_rate": 1.0, "we_rate": 0.7, "you_rate": 0.7,
            "numbers": 0.8, "questions": 0.6, "exclaims": 0.3, "emoji": 0.3,
            "dashes": 0.3, "long_words": 1.5, "hook_len": 15}


def split_posts(raw):
    return [p.strip() for p in re.split(r"(?m)^\s*-{3,}\s*$", raw) if p.strip()]


def features(text):
    words = WORD_RE.findall(text)
    n = max(len(words), 1)
    per100 = lambda c: 100.0 * c / n
    sents = [s for s in SENT_RE.findall(text) if len(s.split()) >= 1]
    slens = [len(s.split()) for s in sents] or [0]
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()] or [text]
    lower = [w.lower().replace("\u2019", "'") for w in words]
    c = Counter(lower)
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    return {
        "sent_len": statistics.mean(slens),
        "sent_sd": statistics.pstdev(slens) if len(slens) > 1 else 0.0,
        "para_sents": len(sents) / len(paras),
        "words": float(len(words)),
        "contractions": per100(len(CONTRACTION_RE.findall(text.replace("\u2019", "'")))),
        "i_rate": per100(c["i"] + c["me"] + c["my"] + c["i'm"] + c["i've"] + c["i'd"] + c["i'll"]),
        "we_rate": per100(c["we"] + c["our"] + c["us"] + c["we're"] + c["we've"]),
        "you_rate": per100(c["you"] + c["your"] + c["you're"] + c["you've"]),
        "numbers": per100(len(NUM_RE.findall(text))),
        "questions": float(text.count("?")),
        "exclaims": per100(text.count("!")),
        "emoji": per100(len(EMOJI_RE.findall(text))),
        "dashes": per100(text.count("\u2014") + text.count("\u2013") + len(re.findall(r" - ", text))),
        "long_words": per100(sum(1 for w in words if len(w) >= 9)),
        "hook_len": float(len(first_line)),
    }


def build(posts):
    if len(posts) < 3:
        raise SystemExit(f"Need at least 3 past posts, got {len(posts)}.")
    rows = [features(p) for p in posts]
    vocab = Counter()
    for p in posts:
        vocab.update(set(w.lower() for w in WORD_RE.findall(p)))
    prof = {"n_posts": len(posts), "features": {}, "vocab": sorted(vocab)}
    for key, *_ in FEATURES:
        vals = [r[key] for r in rows]
        prof["features"][key] = {"mean": statistics.mean(vals),
                                 "sd": statistics.pstdev(vals)}
    return prof


def score(text, prof):
    f = features(text)
    rows = []
    for key, label, hi, lo in FEATURES:
        m = prof["features"][key]["mean"]
        sd = max(prof["features"][key]["sd"], SD_FLOOR[key])
        z = (f[key] - m) / sd
        s = 100.0 * math.exp(-(z ** 2) / 8.0)  # z=1 -> 88, z=2 -> 61, z=3 -> 32
        rows.append({"feature": label, "draft": round(f[key], 1), "theirs": round(m, 1),
                     "z": round(z, 2), "score": round(s, 1),
                     "fix": (hi if z > 0 else lo) if abs(z) >= 1.5 else ""})
    vocab = set(prof["vocab"])
    foreign = sorted({w for w in (x.lower() for x in WORD_RE.findall(text))
                      if len(w) >= 9 and "'" not in w and w not in vocab})
    mean = statistics.mean(r["score"] for r in rows)
    worst = min(rows, key=lambda r: r["score"])
    total = round(0.7 * mean + 0.3 * worst["score"], 1)
    verdict = "MATCH" if total >= 75 else "DRIFT" if total >= 55 else "OFF-VOICE"
    return {"voice_score": total, "verdict": verdict, "n_posts": prof["n_posts"],
            "features": rows, "words_they_never_use": foreign[:25],
            "weakest": worst["feature"]}


def render(res, out):
    print(f"VOICE MATCH vs {res['n_posts']} of your posts", file=out)
    print("-" * 62, file=out)
    for r in sorted(res["features"], key=lambda r: r["score"]):
        bar = "#" * int(r["score"] / 100 * 20)
        note = f"  -> {r['fix']}" if r["fix"] else ""
        print(f"  {r['feature']:<26}{bar:<20} {r['score']:5.1f}  "
              f"(draft {r['draft']}, you {r['theirs']}){note}", file=out)
    if res["words_they_never_use"]:
        print("\n  Words you have never used in a post: "
              + ", ".join(res["words_they_never_use"]), file=out)
    print("-" * 62, file=out)
    print(f"  VOICE SCORE {res['voice_score']}  {res['verdict']}   "
          f"weakest: {res['weakest']}", file=out)
    if res["n_posts"] < 5:
        print("  (Under 5 sample posts: treat this as rough.)", file=out)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("posts")
    b.add_argument("-o", "--out", default="voice_profile.json")
    s = sub.add_parser("score")
    s.add_argument("draft")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--profile")
    g.add_argument("--posts")
    s.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.cmd == "build":
        prof = build(split_posts(open(a.posts, encoding="utf-8").read()))
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(prof, fh)
        print(f"profile from {prof['n_posts']} posts -> {a.out}")
        return
    prof = (json.load(open(a.profile, encoding="utf-8")) if a.profile
            else build(split_posts(open(a.posts, encoding="utf-8").read())))
    res = score(open(a.draft, encoding="utf-8").read(), prof)
    if a.json:
        print(json.dumps(res, indent=2))
    else:
        render(res, sys.stdout)


if __name__ == "__main__":
    main()
