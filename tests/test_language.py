"""Tests for choosing Dutch or English per selection (#31).

    venv\\Scripts\\python.exe -m unittest discover -s tests -v

The rule is small on purpose. What is tested is that ordinary Dutch and
ordinary English go the right way, that a mix goes to the language with more
of the text, and that anything unclear stays English.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import language  # noqa: E402
from language import detect  # noqa: E402


class Dutch(unittest.TestCase):
    def test_an_everyday_dutch_paragraph_is_dutch(self):
        text = ("Goedemorgen! Vandaag gaan we eerst boodschappen doen bij de "
                "supermarkt om de hoek. Daarna fietsen we naar het park, want "
                "het weer is eindelijk mooi.")
        self.assertEqual(detect(text), "nl")

    def test_a_work_email_in_dutch_with_english_loanwords_is_dutch(self):
        text = ("Hoi Ryan, kun je de meeting van morgen naar donderdag "
                "verplaatsen? Ik heb de deadline voor het project nog niet gehaald.")
        self.assertEqual(detect(text), "nl")

    def test_capitals_and_accents_do_not_matter(self):
        self.assertEqual(detect("DE KAT ZIT OP DE MAT, EN HIJ IS ÉÉN JAAR OUD."), "nl")


class English(unittest.TestCase):
    def test_an_everyday_english_paragraph_is_english(self):
        text = ("Good morning! Today we are going to the shop around the corner "
                "first, and then we will ride our bikes to the park.")
        self.assertEqual(detect(text), "en")

    def test_words_both_languages_share_do_not_tip_it(self):
        # "is", "in", "was", "we", "want", "door" are both Dutch and English.
        self.assertEqual(detect("We want the door in the hall, it was there."), "en")


class Mixed(unittest.TestCase):
    def test_dutch_with_an_english_quote_stays_dutch(self):
        text = ('Hij zei "see you later" en toen liep hij naar de deur, want '
                "hij had geen zin meer in het gesprek.")
        self.assertEqual(detect(text), "nl")

    def test_english_with_a_dutch_phrase_stays_english(self):
        text = ("The Dutch say 'dank je wel' when they thank you, and you will "
                "hear it in every shop in the country.")
        self.assertEqual(detect(text), "en")

    def test_an_even_split_falls_back_to_english(self):
        nl, en = language.scores("de het the a")
        self.assertEqual(nl, en)
        self.assertEqual(detect("de het the a"), "en")


class Short(unittest.TestCase):
    def test_a_short_dutch_phrase_is_dutch(self):
        self.assertEqual(detect("Dank je wel!"), "nl")

    def test_a_short_english_phrase_is_english(self):
        self.assertEqual(detect("Thank you!"), "en")

    def test_one_word_with_no_clue_is_english(self):
        self.assertEqual(detect("Amsterdam"), "en")
        self.assertEqual(detect("OK"), "en")


class Empty(unittest.TestCase):
    def test_empty_text_is_english(self):
        self.assertEqual(detect(""), "en")

    def test_none_is_english(self):
        self.assertEqual(detect(None), "en")

    def test_only_numbers_and_punctuation_is_english(self):
        self.assertEqual(detect("12:30 -- 4,5% (!)"), "en")


class Lists(unittest.TestCase):
    def test_no_word_counts_for_both_languages(self):
        self.assertEqual(language.DUTCH & language.ENGLISH, frozenset())


if __name__ == "__main__":
    unittest.main()
