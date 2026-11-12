"""Which language a selection is in: Dutch or English.

    import language
    language.detect("Vandaag gaan we naar het park.")   # -> "nl"

Decided once per selection, offline, with no dependency. The rule counts the
small words every sentence needs (articles, pronouns, prepositions) that
belong to one language only. Content words are left out: "computer" or
"meeting" turn up in Dutch too. Words that both languages spell the same
("is", "in", "was", "we", "of", "had", "want", "door", "die") count for
neither.

Dutch wins only with more hits than English. A tie, no hits, or empty text
gives "en", because English is what cufflink read before this module existed.
"""

import re

DUTCH = frozenset("""
    de het een en niet ook maar dat wat wie waar hoe waarom wanneer
    ik jij je u hij zij ze wij jullie mij mijn jouw jou zijn haar ons onze hun hen
    van voor met naar bij uit aan tot om op over onder tussen zonder tegen
    deze dit die daar hier er nog al wel geen niets iets iemand niemand
    heb hebt heeft hebben ben bent zijn wordt worden werd kan kunnen moet
    moeten wil willen zal zullen zou zouden ga gaat gaan doe doet doen
    als dan toen omdat dus want maar of hoewel terwijl
    heel erg veel meer minder alleen even weer nu straks gisteren vandaag morgen
    ja nee graag alsjeblieft dank bedankt goedemorgen hallo hoi doei
""".split()) - {"want", "of", "die", "even",
                # Also English words: "er" (a pause), "bent", "heel", "hen",
                # "hoe", "doe", "tot".
                "er", "bent", "heel", "hen", "hoe", "doe", "tot"}

ENGLISH = frozenset("""
    the a an and not also but that what who where how why when
    i you he she they it me my your him her our their them us its
    from with to at for by about into onto under between without against
    this these those there here yet any no none nothing something someone
    have has having am are be been being will would shall should can could
    must may might do does did done go goes going gone
    if then because so though although while
    very much many more less only just now soon yesterday today tomorrow
    yes please thanks thank hello hi bye
""".split()) - {"me", "so"}

# Letters, with the accents Dutch uses (ë in "geëerd", é in "één").
_WORD = re.compile(r"[a-zà-ÿ]+(?:'[a-z]+)?")


def scores(text: str) -> tuple[int, int]:
    """(Dutch hits, English hits) for the words in `text`."""
    words = _WORD.findall((text or "").lower())
    nl = sum(word in DUTCH for word in words)
    en = sum(word in ENGLISH for word in words)
    return nl, en


def detect(text: str) -> str:
    """"nl" when the selection reads as Dutch, otherwise "en"."""
    nl, en = scores(text)
    return "nl" if nl > en else "en"
