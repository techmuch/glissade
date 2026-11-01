import sys

import pytest

from glissade import upgrade
from glissade.upgrade import BadRequirement, is_newer, parse_version, satisfies


@pytest.mark.parametrize("text, expected", [
    ("1.2.3", ((1, 2, 3), 1)),
    ("1.2", ((1, 2), 1)),
    ("1.2.0", ((1, 2), 1)),             # trailing zeros don't count
    ("0.15.0rc1", ((0, 15), 0)),
    ("2.0.0+local", ((2,), 1)),
    (" 3 ", ((3,), 1)),
    ("2026.11.1.0", ((2026, 11, 1), 1)),
    ("2026.11.1.2", ((2026, 11, 1, 2), 1)),
    ("v2026.11.1.2", ((2026, 11, 1, 2), 1)),   # git tag form
    ("0", ((0,), 1)),
])
def test_parse_version(text, expected):
    assert parse_version(text) == expected


def test_calendar_versions_compare_on_every_part():
    # The release counter is the fourth part; it must not be ignored.
    assert is_newer("2026.11.1.1", "2026.11.1.0")
    assert is_newer("2026.11.2.0", "2026.11.1.9")
    assert is_newer("2026.12.1.0", "2026.11.30.3")
    assert not is_newer("2026.11.1", "2026.11.1.0")    # the same release
    # The switch from 0.x: every calendar release is newer.
    assert is_newer("2026.11.1.0", "0.15.0")


@pytest.mark.parametrize("req, ok", [
    (">=0.15", True),          # decks written for 0.x keep working
    (">=2026.11.1", True),
    (">=2026.11.1.0", True),
    (">=2026.11.1.1", False),
    ("<2027", True),
    ("==2026.11.1", True),
])
def test_calendar_requirements(req, ok):
    assert satisfies("2026.11.1.0", req) is ok


def test_prerelease_sorts_below_its_release():
    assert is_newer("0.16.0", "0.16.0rc1")
    assert not is_newer("0.16.0rc1", "0.16.0")
    assert is_newer("0.10.0", "0.9.9")   # numeric, not string, comparison


@pytest.mark.parametrize("req, ok", [
    ("0.15", True),            # a bare version means "at least"
    (">=0.15", True),
    (">=0.16", False),
    (">0.15.0", False),
    ("<1.0", True),
    (">=0.6,<1.0", True),
    (">=0.6, <0.15", False),
    ("==0.15.0", True),
    ("!=0.15.0", False),
    ("<=0.15", True),
])
def test_satisfies(req, ok):
    assert satisfies("0.15.0", req) is ok


@pytest.mark.parametrize("req", ["", " , ", ">=", "latest", ">=x.y"])
def test_unreadable_requirements_raise(req):
    with pytest.raises(BadRequirement):
        satisfies("0.15.0", req)


def test_detect_installer_recognises_uv_and_pipx(monkeypatch):
    monkeypatch.setattr(sys, "prefix", "/home/me/.local/share/uv/tools/glissade")
    assert upgrade.detect_installer().command == ["uv", "tool", "upgrade", "glissade"]
    monkeypatch.setattr(sys, "prefix", r"C:\Users\me\pipx\venvs\glissade")
    assert upgrade.detect_installer().kind == "pipx"


def test_detect_installer_falls_back_to_this_interpreters_pip(monkeypatch):
    monkeypatch.setattr(sys, "prefix", "/opt/venv")
    monkeypatch.setattr(upgrade, "_is_user_site", lambda: False)
    inst = upgrade.detect_installer()
    assert inst.kind == "pip"
    assert inst.command[:3] == [sys.executable, "-m", "pip"]


def test_latest_version_reports_why_it_failed(monkeypatch):
    import urllib.error

    def not_found(*a, **k):
        raise urllib.error.HTTPError(upgrade.PYPI_URL, 404, "nf", None, None)

    def offline(*a, **k):
        raise urllib.error.URLError("no route")

    monkeypatch.setattr(upgrade.urllib.request, "urlopen", not_found)
    assert upgrade.latest_version() == (None, upgrade.NOT_PUBLISHED)
    monkeypatch.setattr(upgrade.urllib.request, "urlopen", offline)
    assert upgrade.latest_version() == (None, upgrade.UNREACHABLE)
