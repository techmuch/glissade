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


async def test_remote_navigation_updates_projector(tmp_path: Path, sample_deck_data: dict):
    with running_server(tmp_path, sample_deck_data) as server:
        async with open_pages(server["base_url"]) as (projector, remote):
            await expect(projector.locator(".slide.active")).to_contain_text("Welcome to Glissade")
            await expect(remote.locator("#count")).to_have_text("1 / 2")

            await remote.locator("#next").click()

            await expect(remote.locator("#count")).to_have_text("2 / 2")
            await expect(projector.locator(".slide.active")).to_contain_text("Self-contained decks")

            await remote.locator("#prev").click()

            await expect(remote.locator("#count")).to_have_text("1 / 2")
            await expect(projector.locator(".slide.active")).to_contain_text("Welcome to Glissade")


async def test_live_notes_round_trip_to_remote_and_projector(tmp_path: Path, sample_deck_data: dict):
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

            await expect(projector.locator(".slide.active")).to_contain_text("Welcome to Glissade")
            await expect(remote.locator("#nowtitle")).to_have_text("Welcome Slide")

            data = json.loads(deck_path.read_text(encoding="utf-8"))
            data["slides"][0]["heading"] = "Updated from watch mode"
            data["slides"][0]["title"] = "Updated Slide Title"
            deck_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

            await expect(projector.locator(".slide.active")).to_contain_text("Updated from watch mode")
            await expect(remote.locator("#nowtitle")).to_have_text("Updated Slide Title")


async def test_notes_drawer_lists_captured_notes_and_jumps(tmp_path: Path, sample_deck_data: dict):
    with running_server(tmp_path, sample_deck_data) as server:
        async with open_pages(server["base_url"]) as (_, remote):
            await remote.locator("#livenotes").fill("Remember the intro story")
            await expect(remote.locator("#lnstatus")).to_have_text("Saved for this slide.")

            await remote.locator("#next").click()
            await expect(remote.locator("#count")).to_have_text("2 / 2")

            await remote.locator("#notesbtn").click()
            await expect(remote.locator("#drawertitle")).to_have_text("All captured notes")
            await expect(remote.locator("#lnreviewpanel")).to_contain_text("Remember the intro story")

            await remote.locator("#lnreviewpanel button[data-n='1']").click()
            await expect(remote.locator("#count")).to_have_text("1 / 2")
