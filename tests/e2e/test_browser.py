from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

import pytest
from playwright.async_api import Page, async_playwright, expect

pytestmark = [pytest.mark.e2e, pytest.mark.anyio]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_http(url: str, timeout: float = 15.0) -> None:
    import urllib.request

    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # pragma: no cover - only on startup failure
            last_error = exc
            time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


@contextmanager
def running_server(tmp_path: Path, sample_deck_data: dict):
    decks_dir = tmp_path / "decks"
    decks_dir.mkdir(parents=True, exist_ok=True)
    deck_path = decks_dir / "talk.json"
    deck_path.write_text(json.dumps(sample_deck_data, indent=2), encoding="utf-8")

    port = _free_port()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path("src").resolve())
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "glissade",
            "start",
            "-C",
            str(tmp_path),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_http(base_url + "/")
        yield {
            "base_url": base_url,
            "deck_path": deck_path,
            "proc": proc,
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover
            proc.kill()
            proc.wait(timeout=5)


async def _goto_projector(page: Page, url: str) -> None:
    await page.goto(url, wait_until="domcontentloaded")
    await expect(page.locator(".slide.active")).to_have_count(1)


async def _goto_remote(page: Page, url: str) -> None:
    await page.goto(url, wait_until="domcontentloaded")
    await expect(page.locator("#nowtitle")).not_to_have_text("Connecting…")


@asynccontextmanager
async def open_pages(base_url: str):
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch()
    projector = await browser.new_page(viewport={"width": 1440, "height": 900})
    remote = await browser.new_page(viewport={"width": 430, "height": 932})

    try:
        await _goto_projector(projector, base_url + "/")
        await _goto_remote(remote, base_url + "/control")
        yield projector, remote
    finally:
        await browser.close()
        await playwright.stop()


async def test_remote_navigation_updates_projector(
    tmp_path: Path, sample_deck_data: dict
):
    with running_server(tmp_path, sample_deck_data) as server:
        async with open_pages(server["base_url"]) as (projector, remote):
            active_slide = projector.locator(".slide.active")
            await expect(active_slide).to_contain_text("Welcome to Glissade")
            await expect(remote.locator("#count")).to_have_text("1 / 2")

            await remote.locator("#next").click()

            await expect(remote.locator("#count")).to_have_text("2 / 2")
            await expect(active_slide).to_contain_text("Self-contained decks")

            await remote.locator("#prev").click()

            await expect(remote.locator("#count")).to_have_text("1 / 2")
            await expect(active_slide).to_contain_text("Welcome to Glissade")


async def test_live_notes_round_trip_to_remote_and_projector(
    tmp_path: Path, sample_deck_data: dict
):
    with running_server(tmp_path, sample_deck_data) as server:
        async with open_pages(server["base_url"]) as (projector, remote):
            note = "Ask about rollout timing"
            await remote.locator("#livenotes").fill(note)
            await expect(remote.locator("#lnstatus")).to_have_text("Saving…")
            await expect(remote.locator("#lnstatus")).to_have_text("Saved for this slide.")

            await remote.locator("#showlive").click()

            await expect(projector.locator("#livenotes")).to_have_class("on")
            await expect(projector.locator("#lnbody")).to_contain_text(note)


async def test_live_reload_refreshes_open_pages(tmp_path: Path, sample_deck_data: dict):
    with running_server(tmp_path, sample_deck_data) as server:
        async with open_pages(server["base_url"]) as (projector, remote):
            deck_path = server["deck_path"]

            active_slide = projector.locator(".slide.active")
            await expect(active_slide).to_contain_text("Welcome to Glissade")
            await expect(remote.locator("#nowtitle")).to_have_text("Welcome Slide")

            data = json.loads(deck_path.read_text(encoding="utf-8"))
            data["slides"][0]["heading"] = "Updated from watch mode"
            data["slides"][0]["title"] = "Updated Slide Title"
            deck_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

            await expect(active_slide).to_contain_text("Updated from watch mode")
            await expect(remote.locator("#nowtitle")).to_have_text("Updated Slide Title")


async def test_notes_drawer_lists_captured_notes_and_jumps(
    tmp_path: Path, sample_deck_data: dict
):
    with running_server(tmp_path, sample_deck_data) as server:
        async with open_pages(server["base_url"]) as (_, remote):
            await remote.locator("#livenotes").fill("Remember the intro story")
            await expect(remote.locator("#lnstatus")).to_have_text("Saved for this slide.")

            await remote.locator("#next").click()
            await expect(remote.locator("#count")).to_have_text("2 / 2")

            await remote.locator("#notesbtn").click()
            await expect(remote.locator("#drawertitle")).to_have_text("All captured notes")
            review_panel = remote.locator("#lnreviewpanel")
            await expect(review_panel).to_contain_text("Remember the intro story")

            await remote.locator("#lnreviewpanel button[data-n='1']").click()
            await expect(remote.locator("#count")).to_have_text("1 / 2")


async def test_deck_picker_overlay_keyboard_navigation_and_switching(
    tmp_path: Path, sample_deck_data: dict
):
    decks_dir = tmp_path / "decks"
    decks_dir.mkdir(parents=True, exist_ok=True)
    appendix_deck = {
        "title": "Appendix Talk",
        "format": 1,
        "glissade": ">=0.6",
        "slides": [
            {
                "title": "Appendix First Slide",
                "layout": "title",
                "heading": "Appendix Headline",
                "body": "<p>Deep dive material.</p>",
                "notes": "Extra material.",
            }
        ],
    }
    (decks_dir / "appendix.json").write_text(
        json.dumps(appendix_deck, indent=2), encoding="utf-8"
    )

    with running_server(tmp_path, sample_deck_data) as server:
        async with open_pages(server["base_url"]) as (projector, remote):
            picker = projector.locator("#deckpicker")
            await expect(picker).not_to_have_class("on")

            # Press 'd' to open deck picker
            await projector.keyboard.press("d")
            await expect(picker).to_have_class("on")
            await expect(projector.locator(".dp-title")).to_have_text("Switch Deck")
            await expect(projector.locator(".dp-item")).to_have_count(2)

            # Press 'Escape' to dismiss without switching
            await projector.keyboard.press("Escape")
            await expect(picker).not_to_have_class("on")

            # Re-open picker with 'd'
            await projector.keyboard.press("d")
            await expect(picker).to_have_class("on")

            # Click the inactive deck
            other_item = projector.locator(".dp-item:not(.active)")
            other_name = await other_item.locator(".dp-name").inner_text()
            await other_item.click()

            # Picker closes upon selection
            await expect(picker).not_to_have_class("on")

            # Projector reloads and renders the new deck
            active_slide = projector.locator(".slide.active")
            if "Appendix" in other_name:
                await expect(active_slide).to_contain_text("Appendix Headline")
                await expect(remote.locator("#nowtitle")).to_have_text("Appendix First Slide")
            else:
                await expect(active_slide).to_contain_text("Welcome to Glissade")
                await expect(remote.locator("#nowtitle")).to_have_text("Welcome Slide")



# ------------------------------------------------- design blocks and access


def _design_deck() -> dict:
    return {
        "title": "Design Deck",
        "format": 1,
        "theme": "parchment",
        "slides": [
            {
                "title": "Keys",
                "layout": "cards",
                "numbered": True,
                "eyebrow": "How",
                "heading": "Three keys",
                "cards": [
                    {"title": "Seek", "body": "Pray first.", "source": "Moroni 10:5"},
                    {"title": "Ask", "body": "Bring questions."},
                    {"title": "Live", "body": "Act on it."},
                ],
                "callout": "<b>This week:</b> try one.",
                "source": "Chapter 2",
                "notes": "n",
            },
            {
                "title": "Quote",
                "layout": "quote",
                "cls": "ask",
                "heading": "Why",
                "quote": "Scripture fills us with faith.",
                "cite": "An apostle",
                "subheading": "Discuss",
                "body": "<p>When has it?</p>",
                "notes": "n",
            },
        ],
    }


async def test_design_blocks_render_with_semantic_structure(tmp_path: Path):
    with running_server(tmp_path, _design_deck()) as server:
        async with open_pages(server["base_url"]) as (projector, remote):
            slide = projector.locator(".slide.active")
            # Each slide is a labelled group, announced on change.
            await expect(slide).to_have_attribute("aria-roledescription", "slide")
            await expect(slide).to_have_attribute("aria-label", "1 of 2: Three keys")
            announce = projector.locator("#announce")
            await expect(announce).to_have_text("Slide 1 of 2: Three keys")

            # Numbered cards are an ordered list; the big numerals are hidden
            # from assistive tech because the list already conveys order.
            await expect(slide.locator("ol.cards > li.card")).to_have_count(3)
            numeral = slide.locator(".card-n").first
            await expect(numeral).to_have_attribute("aria-hidden", "true")
            await expect(slide.locator(".card h3").first).to_have_text("Seek")

            # The callout is the last content block whatever the field order.
            last = slide.locator(":scope > :not(.num):not(.source)").last
            await expect(last).to_have_class("callout")
            await expect(last).to_have_attribute("role", "note")
            await expect(slide.locator("footer.source")).to_have_text("Chapter 2")

            # The deck's declared theme is applied.
            accent = await projector.evaluate(
                "getComputedStyle(document.documentElement).getPropertyValue('--paper').trim()"
            )
            assert accent.lower() == "#f7f1e6"

            # The remote previews cards and flags the discussion slide next.
            await expect(remote.locator("#nextrender .pv-card")).to_have_count(0)
            await expect(remote.locator("#nextlabel .badge")).to_have_text("Discussion")

            await remote.locator("#next").click()
            await expect(projector.locator("#announce")).to_have_text("Slide 2 of 2: Why")
            quote = projector.locator(".slide.active figure.pull")
            await expect(quote.locator("blockquote")).to_contain_text("faith")
            await expect(quote.locator("figcaption cite")).to_have_text("An apostle")


async def test_help_overlay_hides_itself_and_toggles(tmp_path: Path, sample_deck_data: dict):
    with running_server(tmp_path, sample_deck_data) as server:
        async with open_pages(server["base_url"]) as (projector, _):
            help_el = projector.locator("#help")
            await expect(help_el).not_to_have_class("on", timeout=8000)
            await projector.keyboard.press("?")
            await expect(help_el).to_have_class("on")
            await projector.keyboard.press("Escape")
            await expect(help_el).not_to_have_class("on")


async def test_deck_picker_moves_and_returns_focus(tmp_path: Path, sample_deck_data: dict):
    decks_dir = tmp_path / "decks"
    decks_dir.mkdir(parents=True, exist_ok=True)
    (decks_dir / "other.json").write_text(json.dumps(
        {"title": "Other", "slides": [{"layout": "title", "heading": "O", "notes": "n"}]}
    ))
    with running_server(tmp_path, sample_deck_data) as server:
        async with open_pages(server["base_url"]) as (projector, _):
            await projector.keyboard.press("d")
            await expect(projector.locator("#dplist")).to_be_focused()
            active = await projector.locator("#dplist").get_attribute("aria-activedescendant")
            assert active and active.startswith("dp-opt-")
            await projector.keyboard.press("ArrowDown")
            moved = await projector.locator("#dplist").get_attribute("aria-activedescendant")
            assert moved != active
            await projector.keyboard.press("Escape")
            await expect(projector.locator("#dplist")).not_to_be_focused()


async def test_remote_exposes_state_to_assistive_tech(tmp_path: Path, sample_deck_data: dict):
    with running_server(tmp_path, sample_deck_data) as server:
        async with open_pages(server["base_url"]) as (_, remote):
            await expect(remote.locator("#dot")).to_have_attribute("aria-label", "Connected")
            blank = remote.locator("#blankbtn")
            await expect(blank).to_have_attribute("aria-pressed", "false")
            await blank.click()
            await expect(blank).to_have_attribute("aria-pressed", "true")

            jump = remote.locator("#jumpbtn")
            await jump.click()
            await expect(jump).to_have_attribute("aria-expanded", "true")
            await expect(remote.locator("#drawer")).to_have_attribute("role", "dialog")
            await expect(remote.locator(".row.cur")).to_be_focused()
            await expect(remote.locator(".row.cur")).to_have_attribute("aria-current", "step")
            await remote.keyboard.press("Escape")
            await expect(remote.locator("#drawer")).not_to_have_class("on")
            await expect(jump).to_be_focused()
            await expect(jump).to_have_attribute("aria-expanded", "false")


async def test_pages_send_the_control_key_from_their_url(
    tmp_path: Path, sample_deck_data: dict
):
    with running_server(tmp_path, sample_deck_data) as server:
        base = server["base_url"]
        async with open_pages(base) as (projector, remote):
            await _goto_remote(remote, base + "/control?k=abc123")
            async with remote.expect_request(
                lambda r: r.url.endswith("/api/next") and r.method == "POST"
            ) as sent:
                await remote.locator("#next").click()
            assert (await (await sent.value).all_headers()).get("x-glissade-key") == "abc123"

            await _goto_projector(projector, base + "/?k=abc123")
            async with projector.expect_request(
                lambda r: r.url.endswith("/api/goto") and r.method == "POST"
            ) as sent:
                await projector.keyboard.press("Home")
            assert (await (await sent.value).all_headers()).get("x-glissade-key") == "abc123"


async def test_remote_says_so_when_its_key_is_refused(
    tmp_path: Path, sample_deck_data: dict
):
    with running_server(tmp_path, sample_deck_data) as server:
        async with open_pages(server["base_url"]) as (_, remote):
            async def refuse(route):
                if route.request.method == "POST":
                    await route.fulfill(status=403, json={"detail": "missing key"})
                else:
                    await route.continue_()

            await remote.route("**/api/**", refuse)
            warn = remote.locator("#keywarn")
            await expect(warn).not_to_be_visible()
            await remote.locator("#next").click()
            await expect(warn).to_be_visible()


DECK_THEME = {
    "name": "Q3",
    "palette": {"dark": "#1b2a41", "light": "#f7f4ee", "accent": "#c8553d"},
    "vars": {"--card-bg": "#010203"},
}


async def _root_var(page: Page, name: str, value: str, equal: bool = True) -> None:
    """Wait until a theme token on :root is (or stops being) `value`."""
    await page.wait_for_function(
        """([n, v, eq]) => {
             const got = getComputedStyle(document.documentElement).getPropertyValue(n).trim();
             return eq ? got === v : got !== v;
           }""",
        arg=[name, value, equal],
        timeout=5000,
    )


async def test_deck_theme_styles_the_projector_and_follows_the_deck(
    tmp_path: Path, sample_deck_data: dict
):
    (tmp_path / "decks").mkdir(parents=True, exist_ok=True)
    (tmp_path / "decks" / "appendix.json").write_text(json.dumps({
        "title": "Appendix", "order": 200,
        "slides": [{"layout": "title", "heading": "Appendix", "notes": "n"}],
    }), encoding="utf-8")
    data = {**sample_deck_data, "theme": DECK_THEME}

    with running_server(tmp_path, data) as server:
        base = server["base_url"]
        async with open_pages(base) as (projector, remote):
            await _root_var(projector, "--paper", "#f7f4ee")
            await _root_var(projector, "--card-bg", "#010203")

            # The remote offers it, labelled as this deck's.
            swatch = remote.locator('.sw[data-id="deck:talk"]')
            await expect(swatch).to_have_count(1)
            await expect(swatch).to_contain_text("Q3 (this deck)")
            await expect(swatch).to_have_attribute("aria-pressed", "true")

            # Switching to a shared theme clears the deck-only token.
            await remote.request.post(base + "/api/theme", data={"id": "paper"})
            await _root_var(projector, "--card-bg", "#010203", equal=False)
            await _root_var(projector, "--paper", "#f7f4ee", equal=False)

            # Another deck doesn't offer it; the remote's list follows.
            await remote.request.post(base + "/api/deck", data={"id": "appendix"})
            await expect(remote.locator('.sw[data-id="deck:talk"]')).to_have_count(0)
            await expect(remote.locator('.sw[data-id="paper"]')).to_have_count(1)


async def test_offline_build_opens_in_the_deck_theme(tmp_path: Path, sample_deck_data: dict):
    decks = tmp_path / "decks"
    decks.mkdir(parents=True, exist_ok=True)
    (decks / "talk.json").write_text(
        json.dumps({**sample_deck_data, "theme": DECK_THEME}), encoding="utf-8")
    out = tmp_path / "build"
    env = dict(os.environ, PYTHONPATH=str(Path("src").resolve()))
    subprocess.run(
        [sys.executable, "-m", "glissade", "build", "-C", str(tmp_path), "-o", str(out)],
        check=True, env=env, capture_output=True,
    )
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch()
    try:
        page = await browser.new_page()
        await _goto_projector(page, (out / "talk.html").as_uri())
        await _root_var(page, "--paper", "#f7f4ee")
        await _root_var(page, "--card-bg", "#010203")
    finally:
        await browser.close()
        await playwright.stop()
