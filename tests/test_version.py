import json

from glissade import SCHEMA_FILE, __version__


def test_schema_stamp_matches_the_release():
    """`check` compares a project's schema copy by this stamp, so a release
    that forgets to bump it would never tell anyone their copy is stale."""
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    assert schema["x-glissade-version"] == __version__


def test_version_is_an_unpadded_calendar_version():
    """year.month.day.release, as PyPI will normalise it: a padded "2026.01.05"
    would be published as 2026.1.5 and stop matching the tag and --version."""
    import datetime
    import re

    m = re.fullmatch(r"(\d{4})\.([1-9]\d?)\.([1-9]\d?)\.(0|[1-9]\d*)", __version__)
    assert m, f"{__version__!r} is not year.month.day.release"
    year, month, day, _ = (int(g) for g in m.groups())
    datetime.date(year, month, day)  # raises on an impossible date
