"""Design building blocks: themes, new layouts and fields, checks and tips."""

import json
from pathlib import Path

import pytest

from glissade import themes as T
from glissade.app import load_themes, render_deck
from glissade.build import build_deck
from glissade.check import check_deck, check_slides, check_themes
from glissade.project import DEFAULT_THEMES
from glissade.shoot import parse_selection

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00"
    b"\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def levels(issues, level):
    return [str(i) for i in issues if i.level == level]


# ------------------------------------------------------------------ themes


def test_contrast_ratio_matches_wcag_reference_values():
    assert T.contrast("#000000", "#ffffff") == pytest.approx(21.0)
    assert T.contrast("#777777", "#ffffff") == pytest.approx(4.48, abs=0.01)
    assert T.contrast("rgba(0,0,0,.5)", "#fff") is None


def test_every_built_in_theme_passes_aa():
    for theme in T.load(DEFAULT_THEMES):
        assert T.contrast_issues(theme) == [], theme["id"]


def test_palette_shorthand_derives_readable_tokens():
    # A mid-tone accent that fails on its own against the light background.
    vars_ = T.expand_palette({"dark": "#202020", "light": "#fafafa", "accent": "#e0a040"})
    assert T.contrast(vars_["--accent"], vars_["--paper"]) >= 4.5
    assert T.contrast(vars_["--ask-accent"], vars_["--ask-bg"]) >= 4.5
    assert T.contrast(vars_["--callout-ink"], vars_["--callout-bg"]) >= 4.5
    assert T.contrast_issues({"vars": vars_}) == []


def test_explicit_vars_override_the_palette(tmp_path):
    (tmp_path / "themes.json").write_text(json.dumps([{
        "id": "mine", "name": "Mine",
        "palette": {"dark": "#111111", "light": "#eeeeee", "accent": "#335577"},
        "vars": {"--accent": "#123456"},
    }]))
    [theme] = T.load(tmp_path / "themes.json")
    assert theme["vars"]["--accent"] == "#123456"
    assert theme["vars"]["--paper"] == "#eeeeee"


def test_theme_font_files_are_embedded_but_paths_never_leave(tmp_path):
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    (fonts / "Face.woff2").write_bytes(b"wOF2fakefontdata")
    (tmp_path / "themes.json").write_text(json.dumps([{
        "id": "branded", "name": "Branded", "vars": {"--display-font": "'Face', serif"},
        "fonts": [{"family": "Face", "src": "fonts/Face.woff2", "weight": "400 700"}],
    }]))
    themes = T.load(tmp_path / "themes.json")
    html = render_deck([{"layout": "title", "heading": "Hi"}], live=False, themes=themes)
    assert '@font-face{font-family:"Face";src:url(data:font/woff2;base64,' in html
    assert str(tmp_path) not in html
    assert T.public(themes)[0]["fonts"] == ["Face"]


def test_low_contrast_project_theme_is_reported():
    issues = check_themes([{"id": "murky", "vars": {"--ink": "#888888", "--paper": "#999999"}}])
    assert any("body text" in str(i) for i in issues)


# ------------------------------------------------------------ deck theme


def test_deck_theme_reaches_the_page(sample_deck_file):
    data = json.loads(sample_deck_file.read_text())
    data["theme"] = "parchment"
    sample_deck_file.write_text(json.dumps(data))
    from glissade.decks import read_deck

    deck = read_deck(sample_deck_file)
    assert deck["theme"] == "parchment"
    html = build_deck(deck, sample_deck_file.parent.parent / "build").path.read_text()
    assert 'const DECK_THEME = "parchment";' in html


def test_unknown_deck_theme_is_a_warning(sample_deck_file):
    from glissade.decks import read_deck

    data = json.loads(sample_deck_file.read_text())
    data["theme"] = "parchmnet"
    sample_deck_file.write_text(json.dumps(data))
    issues = check_deck(read_deck(sample_deck_file), ["paper", "parchment"])
    assert any("unknown theme 'parchmnet'" in w and "parchment" in w
               for w in levels(issues, "warning"))


# ------------------------------------------------------------ new layouts


def cards_slide(**extra):
    slide = {
        "layout": "cards", "heading": "Three keys", "numbered": True,
        "cards": [{"title": "One", "body": "a"}, {"title": "Two"}, {"title": "Three"}],
        "notes": "n",
    }
    slide.update(extra)
    return slide


def test_cards_layout_is_valid(tmp_path):
    issues = check_slides([cards_slide()], tmp_path)
    assert levels(issues, "error") == [] and levels(issues, "warning") == []


def test_cards_count_is_enforced(tmp_path):
    issues = check_slides([cards_slide(cards=[{"title": "only"}])], tmp_path)
    assert any("two to four cards" in e for e in levels(issues, "error"))


def test_empty_card_is_an_error(tmp_path):
    issues = check_slides([cards_slide(cards=[{"title": "a"}, {"source": "x"}])], tmp_path)
    errors = levels(issues, "error")
    assert any("card 2" in e and "no title, body or image" in e for e in errors)


def test_card_images_are_inlined_and_checked(tmp_path):
    (tmp_path / "pic.png").write_bytes(PNG)
    slide = cards_slide(cards=[{"title": "a", "image": {"src": "pic.png"}}, {"title": "b"}])
    issues = check_slides([slide], tmp_path)
    assert any("no alt text" in w for w in levels(issues, "warning"))
    deck = {"id": "d", "title": "D", "path": str(tmp_path / "d.json"), "slides": [slide]}
    html = build_deck(deck, tmp_path / "build").path.read_text()
    assert "data:image/png;base64," in html


def test_quote_layout_needs_a_quote(tmp_path):
    issues = check_slides([{"layout": "quote", "heading": "h", "notes": "n"}], tmp_path)
    assert any("quote layout with no `quote`" in e for e in levels(issues, "error"))


def test_callout_on_a_layout_that_cannot_draw_it_warns(tmp_path):
    slide = {"layout": "section", "heading": "Part two", "callout": "x", "notes": "n"}
    issues = check_slides([slide], tmp_path)
    assert any("`callout` doesn't render" in w for w in levels(issues, "warning"))


def test_scrim_and_focus_are_validated(tmp_path):
    (tmp_path / "pic.png").write_bytes(PNG)
    slide = {
        "layout": "media-full", "heading": "h", "scrim": "top", "notes": "n",
        "image": {"src": "pic.png", "alt": "", "focus": "javascript:alert(1)"},
    }
    warns = levels(check_slides([slide], tmp_path), "warning")
    assert any("scrim should be" in w for w in warns)
    assert any("focus" in w for w in warns)
    slide["scrim"], slide["image"]["focus"] = "left", "70% 30%"
    assert levels(check_slides([slide], tmp_path), "warning") == []


def test_decorative_image_with_empty_alt_is_fine(tmp_path):
    (tmp_path / "pic.png").write_bytes(PNG)
    slide = {"layout": "media-right", "heading": "h", "notes": "n",
             "image": {"src": "pic.png", "alt": ""}}
    assert levels(check_slides([slide], tmp_path), "warning") == []


# -------------------------------------------------------------- design tips


def test_design_tips_flag_dense_slides(tmp_path):
    slide = {
        "layout": "title-content", "heading": "h", "notes": "n",
        "body": "<p>" + "word " * 45 + "</p>",
        "bullets": [str(i) for i in range(8)],
        "quote": "q",
    }
    tips = levels(check_slides([slide], tmp_path), "tip")
    assert any("body is 45 words" in t for t in tips)
    assert any("8 bullets" in t for t in tips)
    assert any("no `cite`" in t for t in tips)


def test_tip_suggests_cards_for_paired_bullets(tmp_path):
    slide = {"layout": "title-content", "heading": "h", "notes": "n",
             "bullets": [{"text": "a", "sub": "x"}, {"text": "b", "sub": "y"},
                         {"text": "c", "sub": "z"}]}
    assert any("cards" in t for t in levels(check_slides([slide], tmp_path), "tip"))


def test_tips_are_not_warnings(tmp_path):
    slide = {"layout": "title-content", "heading": "h" * 90, "notes": "n"}
    issues = check_slides([slide], tmp_path)
    assert levels(issues, "warning") == [] and levels(issues, "tip")


# --------------------------------------------------------------- rendering


def test_page_carries_accessibility_scaffolding():
    html = render_deck([cards_slide()], live=False, themes=load_themes())
    for marker in (
        'id="announce" class="sr-only" aria-live="polite"',
        "aria-roledescription",
        "prefers-reduced-motion",
        '<main id="stage">',
        'aria-labelledby="dptitle"',
    ):
        assert marker in html


def test_schema_and_checker_agree_on_new_layouts():
    from glissade.check import LAYOUTS

    assert {"cards", "quote"} <= LAYOUTS
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "src/glissade/data/schema.json").read_text()
    )
    assert "card" in schema["$defs"]
    for field in ("callout", "source", "cards", "numbered", "scrim"):
        assert field in schema["$defs"]["slide"]["properties"]
    assert "focus" in schema["$defs"]["image"]["properties"]
    assert "theme" in schema["$defs"]["deckObject"]["properties"]


# ------------------------------------------------------------------- shoot


def test_parse_selection():
    assert parse_selection(None, 3) == [1, 2, 3]
    assert parse_selection("1,3,5-7", 6) == [1, 3, 5, 6]
    assert parse_selection("2-2", 4) == [2]
