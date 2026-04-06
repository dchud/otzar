from catalog.templatetags.bidi import bidi_auto, bidi_text, has_hebrew


class TestHasHebrew:
    def test_hebrew_text(self):
        assert has_hebrew("משנה תורה")

    def test_english_text(self):
        assert not has_hebrew("Mishneh Torah")

    def test_mixed_text(self):
        assert has_hebrew("The משנה תורה commentary")

    def test_empty(self):
        assert not has_hebrew("")

    def test_none(self):
        assert not has_hebrew(None)


class TestBidiText:
    def test_hebrew_gets_rtl(self):
        result = bidi_text("משנה תורה")
        assert 'dir="rtl"' in result
        assert "text-rtl" in result

    def test_english_gets_ltr(self):
        result = bidi_text("Mishneh Torah")
        assert 'dir="ltr"' in result

    def test_empty_passthrough(self):
        assert bidi_text("") == ""

    def test_none_passthrough(self):
        assert bidi_text(None) is None


class TestBidiAuto:
    def test_wraps_with_auto(self):
        result = bidi_auto("some text")
        assert 'dir="auto"' in result

    def test_empty_passthrough(self):
        assert bidi_auto("") == ""
