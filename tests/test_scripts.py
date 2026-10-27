"""Regression tests. Run: python3 -I tests/test_scripts.py (from the skill folder)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import clean  # noqa: E402
import guard  # noqa: E402
import voice  # noqa: E402

EM, EN, ZW = "\u2014", "\u2013", "\u200b"


class Clean(unittest.TestCase):
    def test_original_double_period_bug(self):
        # The original humanizer deleted "Let that sink in." and left "..".
        src = "It\u2019s crucial.\u200b Let that sink in.\n"
        out, rep = clean.clean(src)
        self.assertNotIn("..", out)
        self.assertIn("Let that sink in.", out)          # flagged, not deleted
        self.assertTrue(any(f.get("found", "").lower() == "let that sink in"
                            for f in rep["flags"]))

    def test_em_dash_flagged_not_rewritten(self):
        out, rep = clean.clean(f"We shipped it {EM} late.\n")
        self.assertIn(EM, out)
        self.assertEqual(sum(f["kind"] == "em dash" for f in rep["flags"]), 1)

    def test_en_dash_range_is_fine(self):
        _, rep = clean.clean(f"It took 5{EN}10 days.\n")
        self.assertFalse(any("dash" in f["kind"] for f in rep["flags"]))

    def test_invisible_and_quotes_fixed(self):
        out, rep = clean.clean(f"\u201cHi\u201d{ZW} there\u2026\n")
        self.assertEqual(out, '"Hi" there...\n')
        self.assertTrue(rep["fixed"])

    def test_urls_not_flagged(self):
        _, rep = clean.clean("See https://example.com/leverage-robust-tools\n")
        self.assertEqual(rep["flags"], [])

    def test_line_breaks_preserved(self):
        src = "Line one.\n\nLine two.\n"
        out, _ = clean.clean(src)
        self.assertEqual(out, src)

    def test_phrase_not_double_counted(self):
        _, rep = clean.clean("We need to delve into this.\n")
        self.assertEqual(len([f for f in rep["flags"] if f["kind"].startswith("stock")]), 1)


class Guard(unittest.TestCase):
    T = [("employer", "Acme Bank"), ("codename", "Falcon")]

    def test_employer_plus_metric_blocks(self):
        r = guard.check("At Acme Bank we cut churn by 14%.", self.T)
        self.assertEqual(r["status"], "BLOCK")

    def test_employer_alone_warns(self):
        r = guard.check("I work at Acme Bank.", self.T)
        self.assertEqual(r["status"], "WARN")

    def test_ticket_id_blocks(self):
        self.assertEqual(guard.check("Closed DATA-4821 today.", [])["status"], "BLOCK")

    def test_confidential_blocks(self):
        self.assertEqual(guard.check("This is not public yet.", [])["status"], "BLOCK")

    def test_generic_post_clear(self):
        r = guard.check("Most data teams skip the boring part: naming things well.", [])
        self.assertEqual(r["status"], "CLEAR")

    def test_metric_without_employer_is_not_blocked(self):
        r = guard.check("I read 40 books last year.", self.T)
        self.assertNotEqual(r["status"], "BLOCK")


class Voice(unittest.TestCase):
    POSTS = [
        "I shipped a thing. It broke. I fixed it.\n\nThat's the job, honestly.\n\nWhat's yours?",
        "Short posts win. I don't write essays.\n\nI write what I'd say out loud.",
        "I spent 3 weeks on a dashboard nobody opened.\n\nLesson: ask first. Build second.",
        "I'm not a writer. I'm a builder who writes.\n\nThat's fine. It works.",
    ]

    def test_in_voice_beats_off_voice(self):
        prof = voice.build(self.POSTS)
        mine = voice.score("I built a tool in 2 days. It's ugly. It works.\n\nShip first.", prof)
        other = voice.score(
            "Organizations seeking transformational outcomes must systematically "
            "operationalize comprehensive stakeholder alignment frameworks, thereby "
            "facilitating sustainable, scalable, enterprise-grade capabilities across "
            "interdependent organizational ecosystems and verticals.", prof)
        self.assertGreater(mine["voice_score"], other["voice_score"])
        self.assertIn("operationalize", other["words_they_never_use"])

    def test_needs_three_posts(self):
        with self.assertRaises(SystemExit):
            voice.build(self.POSTS[:2])

    def test_split_posts(self):
        self.assertEqual(len(voice.split_posts("a\n---\nb\n----\nc")), 3)


if __name__ == "__main__":
    unittest.main(verbosity=1)
