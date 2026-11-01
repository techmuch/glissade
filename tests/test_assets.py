from pathlib import Path

from glissade.assets import external_media, media_nodes, prepare_slides
from glissade.check import check_slides


def test_media_nodes_reaches_every_location():
    slide = {
        "image": {"src": "a"},
        "media": {"src": "b"},
        "images": [{"src": "c"}, {"src": "d"}],
        "cards": [{"image": {"src": "e"}}, {"title": "no image"}],
        "left": {"image": {"src": "f"}, "media": {"file": "g"}},
        "right": {"media": {"src": "h"}},
        "quads": [{"image": {"src": "i"}}, {"media": {"src": "j"}}, "junk", {}],
    }
    found = [(kind, where, node.get("src") or node.get("file"))
             for kind, where, node in media_nodes(slide)]
    assert found == [
        ("image", "", "a"), ("media", "", "b"),
        ("image", " image 1", "c"), ("image", " image 2", "d"),
        ("image", " card 1", "e"),
        ("image", " left", "f"), ("media", " left", "g"),
        ("media", " right", "h"),
        ("image", " quad 1", "i"), ("media", " quad 2", "j"),
    ]


def test_media_nodes_ignores_non_dicts():
    assert list(media_nodes("not a slide")) == []
    assert list(media_nodes({"images": None, "cards": "x"})) == []


def test_offline_report_lists_every_remote_image():
    slides = [
        {"n": 1, "layout": "grid", "images": [
            {"src": "https://x.test/a.jpg"}, {"src": "https://x.test/b.jpg"}]},
        {"n": 2, "layout": "cards", "cards": [
            {"title": "t", "image": {"src": "https://x.test/c.jpg"}}, {"title": "u"}]},
        {"n": 3, "layout": "two-content", "left": {"image": {"src": "https://x.test/d.jpg"}},
         "right": {"body": "r"}},
    ]
    prepared, warnings = prepare_slides(slides, Path("."))
    assert len(warnings) == 4
    assert [n for n, _ in external_media(prepared)] == [1, 1, 2, 3]


def test_alt_text_is_checked_on_remote_images():
    issues = check_slides(
        [{"layout": "media-right", "heading": "h", "notes": "n",
          "image": {"src": "https://x.test/a.jpg"}}],
        Path("."),
    )
    assert any("alt text" in i.message for i in issues)


def test_inlined_file_cache_keeps_one_entry_per_path(tmp_path):
    import os

    from glissade import assets

    img = tmp_path / "pic.svg"
    img.write_text("<svg/>", encoding="utf-8")
    first = assets.data_uri(img)
    img.write_text("<svg><g/></svg>", encoding="utf-8")
    os.utime(img, ns=(1, 1))
    second = assets.data_uri(img)
    assert first != second
    assert sum(1 for k in assets._files if k == str(img)) == 1
