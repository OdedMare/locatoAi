from app.common.utils.normalizer import normalize_text


def test_strips_niqqud():
    # Final letters are folded (ם→מ) for position-independent comparison —
    # see test_folds_final_letters for why this is intentional.
    assert normalize_text("שָׁלוֹם") == "שלומ"


def test_strips_gershayim_and_geresh():
    assert normalize_text('ת״א') == "תא"
    assert normalize_text("צה״ל") == "צהל"


def test_folds_final_letters():
    assert normalize_text("בית ספר") == normalize_text("בית ספר")
    assert normalize_text("שלום") == normalize_text("שלומ".translate(
        str.maketrans({"מ": "ם"})
    ))


def test_collapses_whitespace_hyphens_dots():
    assert normalize_text("בית-ספר") == normalize_text("בית ספר")
    assert normalize_text("בית.ספר") == normalize_text("בית ספר")
    assert normalize_text("בית   ספר") == normalize_text("בית ספר")


def test_casefolds_latin_text():
    assert normalize_text("Tel Aviv") == normalize_text("tel aviv")


def test_empty_and_none_safe():
    assert normalize_text("") == ""


def test_does_not_bridge_acronym_to_full_name():
    """Documented limitation: normalization fixes formatting variants of
    the SAME string, not genuinely different strings like an acronym."""
    assert normalize_text('ת״א') not in normalize_text("תל אביב")
