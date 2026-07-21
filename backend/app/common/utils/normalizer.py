"""Normalize Hebrew/mixed text before substring or fuzzy comparison.

Fixes the class of mismatch where the same place/entity name is stored or
typed with different niqqud, punctuation, or final-letter spelling —
e.g. "תל אביב" vs "ת״א", or "בית ספר" vs "בית-ספר". Deterministic and
cheap; always applied before `attribute_filter`'s "contains"/"eq" checks
so existing exact/substring semantics keep working, just on cleaner text.
"""

import re
import unicodedata

# Niqqud (vowel points) and other Hebrew diacritics: U+0591–U+05C7.
_NIQQUD_RE = re.compile(r"[֑-ׇ]")

# Hebrew punctuation marks (gershayim/geresh) plus their common ASCII
# stand-ins, all treated as noise to strip rather than compare.
_HEBREW_PUNCTUATION_RE = re.compile(r"[׳״\"'‘’“”]")

# Final-letter forms folded to their regular counterparts so "בית ספר"-style
# comparisons don't depend on word position (ך→כ, ם→מ, ן→נ, ף→פ, ץ→צ).
_FINAL_LETTERS = str.maketrans({
    "ך": "כ",  # ך → כ
    "ם": "מ",  # ם → מ
    "ן": "נ",  # ן → נ
    "ף": "פ",  # ף → פ
    "ץ": "צ",  # ץ → צ
})

_WHITESPACE_RE = re.compile(r"[\s\-_.]+")


class TextNormalizer:
    @staticmethod
    def normalize(value: str) -> str:
        if not value:
            return ""
        text = unicodedata.normalize("NFKC", value)
        text = _NIQQUD_RE.sub("", text)
        text = _HEBREW_PUNCTUATION_RE.sub("", text)
        text = text.translate(_FINAL_LETTERS)
        text = _WHITESPACE_RE.sub(" ", text)
        return text.strip().casefold()


normalize_text = TextNormalizer.normalize
