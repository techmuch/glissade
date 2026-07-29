from glissade.check import check_requirement, check_slides


def test_check_slides_valid(tmp_path):
    slides = [
        {
            "title": "Slide 1",
            "layout": "title",
            "heading": "Hello",
            "notes": "Speaker notes"
        }
    ]
    issues = check_slides(slides, tmp_path)
    # Filter out warnings if any (e.g. no errors)
    errors = [i for i in issues if i.level == "error"]
    assert len(errors) == 0

def test_check_slides_layout_typo(tmp_path):
    slides = [
        {
            "layout": "media-rite",
            "heading": "Typo Layout",
            "notes": "Notes"
        }
    ]
    issues = check_slides(slides, tmp_path)
    errors = [i for i in issues if i.level == "error"]
    assert len(errors) == 1
    assert "unknown layout 'media-rite'" in errors[0].message
    assert "Did you mean 'media-right'?" in errors[0].hint

def test_check_slides_youtube_watch_link(tmp_path):
    slides = [
        {
            "layout": "media-right",
            "heading": "Video",
            "media": {"src": "https://www.youtube.com/watch?v=12345"},
            "notes": "Notes"
        }
    ]
    issues = check_slides(slides, tmp_path)
    errors = [i for i in issues if i.level == "error"]
    assert any("YouTube watch link will not embed" in e.message for e in errors)

def test_check_slides_missing_notes_warning(tmp_path):
    slides = [
        {
            "layout": "title",
            "heading": "No notes here"
        }
    ]
    issues = check_slides(slides, tmp_path)
    warnings = [i for i in issues if i.level == "warning"]
    assert any("no speaker notes" in w.message for w in warnings)


def test_check_slides_quad_chart_valid(tmp_path):
    slides = [
        {
            "layout": "quad-chart",
            "heading": "Quarterly view",
            "quads": [
                {"subheading": "North", "body": "<p>Steady growth.</p>"},
                {"subheading": "South", "body": "<p>Launch in September.</p>"},
                {"subheading": "East", "body": "<p>Partner-led pipeline.</p>"},
                {"subheading": "West", "body": "<p>Margin recovery.</p>"},
            ],
            "notes": "Talk through each region clockwise."
        }
    ]
    issues = check_slides(slides, tmp_path)
    errors = [i for i in issues if i.level == "error"]
    assert len(errors) == 0


def test_check_slides_quad_chart_requires_four_quads(tmp_path):
    slides = [
        {
            "layout": "quad-chart",
            "heading": "Quarterly view",
            "quads": [
                {"subheading": "North", "body": "<p>Steady growth.</p>"},
                {"subheading": "South", "body": "<p>Launch in September.</p>"},
                {"subheading": "East", "body": "<p>Partner-led pipeline.</p>"},
            ],
            "notes": "Talk through each region clockwise."
        }
    ]
    issues = check_slides(slides, tmp_path)
    errors = [i for i in issues if i.level == "error"]
    assert any("quad-chart needs exactly four `quads`" in e.message for e in errors)

def test_check_requirement_satisfied():
    deck = {"requires": ">=0.1.0"}
    issues = check_requirement(deck)
    assert len(issues) == 0

def test_check_requirement_unmet():
    deck = {"requires": ">=99.0.0"}
    issues = check_requirement(deck)
    assert len(issues) == 1
    assert issues[0].level == "error"
    assert "needs Glissade >=99.0.0" in issues[0].message
