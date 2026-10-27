---
name: li-post
description: >-
  Write a LinkedIn post from a raw idea in the user's own voice, using 21 hook
  formulas, then gate it: confidentiality check, cleanup, and a voice-match
  score against the user's real past posts. Use whenever the user wants a
  LinkedIn post, a hook, a draft for the feed, "post about X", "turn this into
  a LinkedIn post", or hook options. Never publishes; the user posts it.
---

# li-post

Turns one true, specific idea into a LinkedIn post that sounds like the person
whose name is on it, and that will not get them in trouble at work.

Everything this skill needs is in this folder:

```
hooks.json            21 hook formulas
scripts/guard.py      confidentiality gate (employer/client names, metrics, codenames)
scripts/clean.py      fixes invisible characters and curly quotes; flags dashes and stock phrases
scripts/voice.py      scores a draft against the user's own past posts
scripts/slop.json     the stock-phrase list clean.py flags (edit freely)
tests/                regression tests: python3 -I tests/test_scripts.py
```

Run every script with `python3 -I`, passing file paths as arguments. Write the
draft to a scratch file first; never paste post text into a shell command.

## Step 1: Gather three inputs before writing anything

**A. Past posts (voice).** Look in this order and use the first you find:
1. Past posts or a voice profile already in this conversation or the
   project's files (anything like `past_posts.txt`, `linkedin-voice`).
2. `~/.claude/linkedin/past_posts.txt` or `voice_profile.json`, if that folder
   exists (local Claude Code installs).
3. Otherwise ask for **at least 3 of their own past posts, ideally 5 to 10**,
   separated by `---`. If they have never posted, ask for 3 things they wrote
   for humans (emails, Slack messages, a talk) and say the match will be
   rougher.

Never invent a voice. If they decline to share samples, write the draft but
say plainly that it is unscored for voice.

**B. Guard terms.** Same lookup order for `guard.txt`. If none, ask in the
same message as A: "Which employer, clients, products, teams or codenames
should never appear next to a number?" One per line. This is the gate that
protects them; do not skip it to save a turn.

**C. One specific true thing.** If the idea is thin ("post about AI"), ask one
batched question: what happened, to whom, and what did it cost or return.
Get a real number or leave `{{your number}}` in the draft and flag it.

Ask A, B and C in **one** message, then wait.

**Persistence.** If you could not find A or B on disk, save them to the
working directory for this session and tell the user, in one line, that they
will not carry over: to reuse them, add `past_posts.txt` and `guard.txt` to
their Project files (claude.ai) or to `~/.claude/linkedin/` (Claude Code). Do
not claim anything was saved permanently.

## Step 2: Three hooks

Read `hooks.json`. Pick the three formulas that genuinely fit the idea:
different formulas, not variations of one. Show them as three numbered lines
and say which you would ship and why, in one sentence.

Treat each formula's `best_for` note as the original author's rule of thumb,
not a measured fact. Do not repeat those claims to the user as evidence.

## Step 3: Draft

```
Line 1     the hook, alone; survives truncation at about 140 characters.
Line 2     the payoff of line 1, not setup for line 3.
Body       short paragraphs, 1 to 3 lines, blank line between each.
The turn   one line that reframes what came before.
Close      one specific question or one instruction. Never both.
```

Aim for 900 to 1,300 characters unless the user's own posts run shorter or
longer; their norm beats this default. Match their habits: if they never use
emoji or hashtags, do not add them. Three hashtags at most, at the bottom.

## Step 4: The gate (run all three, in this order)

**4a. Confidentiality.**
`python3 -I scripts/guard.py draft.txt --terms guard.txt`

- `BLOCK`: do not present the draft as ready. Show each hit and offer a
  rewrite that generalizes it ("a large US bank", a range instead of the exact
  figure, the lesson without the internal detail). Only keep a blocked item if
  the user confirms it is already public or approved for them to share.
- `WARN`: rewrite if it costs nothing; otherwise list the warnings in the
  receipt so the user decides.
- A clean result means no pattern fired, not that the post is cleared. Say so
  if the post is about their job.

**4b. Cleanup.**
`python3 -I scripts/clean.py draft.txt -o draft.txt`

It auto-fixes only what cannot change meaning (invisible characters, curly
quotes, the ellipsis character). It flags dashes, stock phrases and structural
tells but never rewrites them. **You** rewrite each flagged line by judgement:
a dash becomes a full stop, a colon, a comma or parentheses depending on the
sentence. Rerun until there are no flags, or explain any you kept on purpose.

**4c. Voice match.**
`python3 -I scripts/voice.py score draft.txt --posts past_posts.txt`
(or `--profile voice_profile.json`).

- `MATCH` (75+): ship it.
- `DRIFT` or `OFF-VOICE`: revise the lowest features first, following the
  `->` hints, and swap out any "words you have never used in a post" for words
  they do use. Up to two revisions, then show the best version with the score;
  do not loop forever chasing a number.

Rerun 4a after any rewrite that adds names or numbers.

## Step 5: The receipt

The post in a fenced block, exactly as it should be pasted. Then:

```
POST READY
hook:            #17 Time Anchor
length:          1,140 characters
confidentiality: CLEAR (12 terms checked)      or the warnings, one per line
cleanup:         3 characters fixed, 0 flags left
voice:           81 MATCH vs 6 of your posts (weakest: sentence length)
placeholders:    none                          or each {{your number}} to fill

Reply "yes" to log it, or tell me what to change.
```

If there is a link, it goes in the first comment, not the body; say so in the
receipt.

## Step 6: Never publish

This skill writes; the user posts. Never use a browser or any tool to post to
LinkedIn. On "yes": if `~/.claude/linkedin/` exists, append the date, hook
number and first line to `log.md` there. Otherwise give that one log line back
to the user to keep, and do not claim it was saved.

## Rules

- **One idea per post.** Two ideas means two posts; say so.
- **Numbers over adjectives**, but only the user's real numbers.
- **Never fabricate** metrics, clients, revenue or outcomes, even as a
  placeholder. Unknown means `{{your number}}` plus a flag.
- **No engagement bait.** "Thoughts?" and "Agree?" are out. The closing
  question must be one only this post could ask.
- **The gate is not optional.** Every draft shown as ready has been through
  4a, 4b and 4c, and the receipt reports all three honestly.

## Example

Input: `/li-post we built an internal tool that cut proposal time from 5 hours to 20 min`

```
HOOKS
1. #17 Time Anchor   Writing a proposal used to take me 5 hours. It now takes 20 minutes.
2. #12 Comparison    An expensive proposal writer vs a weekend and a template. The weekend won.
3. #3  Mistake       For two years I billed clients for hours I spent on formatting.

Shipping #17: the ratio is believable and the number is yours.
```

If the draft then said "At Acme Bank our tool cut it to 20 minutes",
guard.py would BLOCK it: an employer named in the same sentence as a number.
A number with no employer named passes the script, so still ask yourself
whether the figure is internal before shipping it.
