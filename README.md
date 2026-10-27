# li-post

A single Claude skill that turns one true, specific idea into a LinkedIn post
in your own voice, then puts the draft through a three-part gate before you
see it:

1. **Confidentiality** (`scripts/guard.py`): blocks a draft that names your
   employer, a client or a codename in the same sentence as a number, plus
   ticket IDs, internal URLs and "not public yet" language.
2. **Cleanup** (`scripts/clean.py`): auto-fixes only what cannot change
   meaning (invisible characters, curly quotes). Dashes and stock phrases are
   flagged for you to rewrite, never mangled by a regex.
3. **Voice match** (`scripts/voice.py`): scores the draft against your own
   past posts, not against a generic "sounds like AI" detector.

It never posts to LinkedIn. It writes; you post.

## Install

Claude Code:

```bash
git clone https://github.com/ranjanvaishnav08/linkedin-post-skill.git ~/.claude/skills/li-post
```

claude.ai: download this repo as a zip and upload it as a skill.

Python 3.8+, standard library only. No network calls.

## Your data stays local

Put your own files in the skill folder or `~/.claude/linkedin/`:

- `past_posts.txt`: 5 to 10 of your posts, separated by a line with `---`
- `guard.txt`: names that must never sit next to a number, one per line
  (`employer: ...`, `client: ...`, `codename: ...`)

Both are in `.gitignore`. Do not commit them.

## Limits, stated plainly

- The guard is a tripwire, not legal review. An internal number with no
  company named in the sentence passes it.
- The voice score is rough with fewer than 5 sample posts.
- The hook notes in `hooks.json` are the original author's rules of thumb,
  not measured results.

## Tests

```bash
python3 -I tests/test_scripts.py
```

## Credit

Derived from [linkedin-agent-skill](https://github.com/avi691/linkedin-agent-skill)
by Jake Schincariol, shared by Avi Grondin, under the MIT License. The hook
formulas (`hooks.json`) and stock-phrase list (`scripts/slop.json`) come from
that project. The guard, voice scorer, cleaner and tests are new.
