"""Tests for volume designation normalization."""

from ingest.series_workflow import normalize_volume_number


class TestArabicDigits:
    """Volume designations written with Arabic digits."""

    def test_plain_integer(self):
        assert normalize_volume_number("3") == "3"

    def test_multi_digit(self):
        assert normalize_volume_number("13") == "13"

    def test_leading_zeros_dropped(self):
        assert normalize_volume_number("03") == "3"

    def test_v_dot_prefix(self):
        assert normalize_volume_number("v. 3") == "3"

    def test_v_dot_prefix_without_space(self):
        assert normalize_volume_number("v.3") == "3"

    def test_vol_dot_prefix(self):
        assert normalize_volume_number("vol. 3") == "3"

    def test_vol_prefix_capitalized_without_period(self):
        assert normalize_volume_number("Vol 3") == "3"

    def test_volume_word_prefix(self):
        assert normalize_volume_number("volume 3") == "3"

    def test_part_prefix(self):
        assert normalize_volume_number("pt. 3") == "3"

    def test_number_prefix(self):
        assert normalize_volume_number("no. 3") == "3"

    def test_surrounding_whitespace(self):
        assert normalize_volume_number("  v. 3  ") == "3"

    def test_trailing_punctuation(self):
        assert normalize_volume_number("v. 3.") == "3"

    def test_part_title_after_colon_ignored(self):
        assert normalize_volume_number("v. 3: The Return") == "3"

    def test_zero_is_not_a_volume_number(self):
        assert normalize_volume_number("v. 0") == ""


class TestRomanNumerals:
    """Volume designations written with Roman numerals."""

    def test_lowercase(self):
        assert normalize_volume_number("iii") == "3"

    def test_uppercase(self):
        assert normalize_volume_number("III") == "3"

    def test_with_prefix(self):
        assert normalize_volume_number("vol. III") == "3"

    def test_subtractive_four(self):
        assert normalize_volume_number("IV") == "4"

    def test_subtractive_nine(self):
        assert normalize_volume_number("ix") == "9"

    def test_six_is_not_read_as_a_v_prefix(self):
        assert normalize_volume_number("VI") == "6"

    def test_teens(self):
        assert normalize_volume_number("xiv") == "14"

    def test_tens(self):
        assert normalize_volume_number("XL") == "40"

    def test_upper_bound(self):
        assert normalize_volume_number("CC") == "200"

    def test_non_canonical_form_rejected(self):
        assert normalize_volume_number("IIII") == ""

    def test_value_above_plausible_volume_range_rejected(self):
        assert normalize_volume_number("MCMLXXXIV") == ""

    def test_english_word_of_roman_letters_rejected(self):
        # "MIX" is a well-formed Roman numeral for 1009, far outside the
        # range a volume designation occupies.
        assert normalize_volume_number("mix") == ""


class TestHebrewGematria:
    """Volume designations written with Hebrew letters."""

    def test_single_letter(self):
        assert normalize_volume_number("ג") == "3"

    def test_single_letter_five(self):
        assert normalize_volume_number("ה") == "5"

    def test_chelek_prefix(self):
        assert normalize_volume_number("חלק ג") == "3"

    def test_sefer_prefix(self):
        assert normalize_volume_number("ספר ג") == "3"

    def test_kerekh_prefix(self):
        assert normalize_volume_number("כרך ג") == "3"

    def test_part_title_after_colon_ignored(self):
        # "כרך ה: ספר אהבה"
        raw = "כרך ה: ספר אהבה"
        assert normalize_volume_number(raw) == "5"

    def test_part_title_after_colon_ignored_sefer(self):
        # "ספר ג: משפטים"
        raw = "ספר ג: משפטים"
        assert normalize_volume_number(raw) == "3"

    def test_eleven(self):
        assert normalize_volume_number("יא") == "11"

    def test_fifteen_uses_tet_vav(self):
        assert normalize_volume_number("טו") == "15"

    def test_sixteen_uses_tet_zayin(self):
        assert normalize_volume_number("טז") == "16"

    def test_fifteen_with_gershayim(self):
        assert normalize_volume_number("ט״ו") == "15"

    def test_sixteen_with_gershayim(self):
        assert normalize_volume_number("ט״ז") == "16"

    def test_fifteen_with_ascii_quote(self):
        assert normalize_volume_number('ט"ו') == "15"

    def test_single_letter_with_geresh(self):
        assert normalize_volume_number("ג׳") == "3"

    def test_single_letter_with_ascii_apostrophe(self):
        assert normalize_volume_number("ג'") == "3"

    def test_fifteen_is_not_spelled_with_yod_heh(self):
        # Naive letter sums would make yod+heh 15, but that spells a
        # divine name and is never used as a numeral.
        assert normalize_volume_number("יה") == ""

    def test_sixteen_is_not_spelled_with_yod_vav(self):
        assert normalize_volume_number("יו") == ""

    def test_twenty(self):
        assert normalize_volume_number("כ") == "20"

    def test_hundred(self):
        assert normalize_volume_number("ק") == "100"

    def test_hundred_fifteen(self):
        assert normalize_volume_number("קטו") == "115"

    def test_hundred_sixteen(self):
        assert normalize_volume_number("קטז") == "116"

    def test_two_hundred(self):
        assert normalize_volume_number("ר") == "200"

    def test_final_letter_form(self):
        # Final mem carries the same value as plain mem.
        assert normalize_volume_number("ם") == "40"

    def test_hebrew_word_rejected(self):
        # "מבוא" (introduction) is letters, not a numeral.
        assert normalize_volume_number("מבוא") == ""


class TestUnparseable:
    """Input carrying no volume number."""

    def test_english_word(self):
        assert normalize_volume_number("Introduction") == ""

    def test_index(self):
        assert normalize_volume_number("index") == ""

    def test_letters(self):
        assert normalize_volume_number("abc") == ""

    def test_prefix_alone(self):
        assert normalize_volume_number("vol.") == ""

    def test_not_applicable(self):
        assert normalize_volume_number("n/a") == ""


class TestEmptyInput:
    """Missing or blank input."""

    def test_empty_string(self):
        assert normalize_volume_number("") == ""

    def test_whitespace_only(self):
        assert normalize_volume_number("   ") == ""

    def test_none(self):
        assert normalize_volume_number(None) == ""
