import shutil
import subprocess

import pytest

from glissade.app import deck_template, render_deck
from glissade.project import TEMPLATE_DIR


def test_template_inlines_its_stylesheet_and_script():
    page = deck_template()
    assert "/*__DECK_CSS__*/" not in page and "/*__DECK_JS__*/" not in page
    assert (TEMPLATE_DIR / "deck.css").read_text(encoding="utf-8") in page
    assert (TEMPLATE_DIR / "deck.js").read_text(encoding="utf-8") in page


def test_every_placeholder_is_filled():
    page = render_deck([{"n": 1, "title": "t", "layout": "title", "heading": "h"}], live=False)
    for token in ("__SLIDES_JSON__", "__THEMES_JSON__", "__DECK_THEME__", "__DECKS_JSON__",
                  "__CURRENT_DECK__", "__TITLE__", "__LIVE__", "/*__FONT_FACES__*/"):
        assert token not in page


def test_slide_text_that_looks_like_a_placeholder_survives():
    slide = {"n": 1, "title": "t", "layout": "title-content",
             "heading": "Name your token __TITLE__ or __LIVE__"}
    page = render_deck([slide], live=True, title="Real title")
    assert "Name your token __TITLE__ or __LIVE__" in page
    assert "const LIVE = true;" in page


def test_script_closing_tag_in_a_slide_cannot_end_the_script():
    page = render_deck([{"n": 1, "title": "t", "layout": "blank",
                         "html": "</script><b>x</b>"}], live=False)
    assert page.count("</script>") == 1


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_deck_script_is_valid_javascript():
    subprocess.run(["node", "--check", str(TEMPLATE_DIR / "deck.js")], check=True)
