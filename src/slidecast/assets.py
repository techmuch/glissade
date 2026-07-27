"""Turn linked media into self-contained media.

Slides reference images and activities by path in slides.json. Before the deck
is rendered — served or built — everything local is pulled inline: images
become data URIs, local HTML activities become iframe `srcdoc`. The result is
one file that works with no network and no sibling directories.

External URLs are the one thing that cannot be inlined. Those keep their src
and get a pre-rendered QR code so that if the room's Wi-Fi is down, the slide
can still show people where the video lives instead of a blank frame.
"""

from __future__ import annotations

import base64
import hashlib
import mimetypes
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# Presentation screens are rarely beyond 4K, and a 12-megapixel phone photo
# base64-encoded would add ~5 MB to the deck for no visible gain.
MAX_IMAGE_EDGE = 2560
JPEG_QUALITY = 82

# Anything larger than this stays untouched rather than silently ballooning the
# deck; the build prints a warning instead.
LARGE_ASSET_WARN = 1_500_000

_cache: dict[tuple, str] = {}


def is_external(src: str) -> bool:
    """True for anything the browser must fetch over the network."""
    if not isinstance(src, str):
        return False
    return src.startswith(("http://", "https://", "//"))


def is_data_uri(src: str) -> bool:
    return isinstance(src, str) and src.startswith("data:")


def _cache_key(path: Path, *extra: Any) -> tuple:
    try:
        st = path.stat()
        return (str(path), st.st_mtime_ns, st.st_size, *extra)
    except OSError:
        return (str(path), None, None, *extra)


def _shrink(raw: bytes, suffix: str) -> tuple[bytes, str]:
    """Downscale oversized images when Pillow is available.

    Returns the original bytes unchanged if Pillow is missing, the image is
    already small enough, or anything goes wrong — a slightly large deck is a
    much better failure than a lesson that won't build.
    """
    try:
        import io

        from PIL import Image  # type: ignore
    except ImportError:
        return raw, suffix

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
        if max(img.size) <= MAX_IMAGE_EDGE and len(raw) <= LARGE_ASSET_WARN:
            return raw, suffix

        img.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.LANCZOS)
        buf = io.BytesIO()
        if suffix.lower() in (".png", ".gif", ".webp") and img.mode in ("RGBA", "LA", "P"):
            # Keep transparency; PNG is the safe container for it.
            img.convert("RGBA").save(buf, format="PNG", optimize=True)
            return buf.getvalue(), ".png"
        img.convert("RGB").save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return buf.getvalue(), ".jpg"
    except Exception:
        return raw, suffix


def data_uri(path: Path, warnings: list[str] | None = None) -> str | None:
    """Read a local file and return it as a data: URI, or None if unreadable."""
    key = _cache_key(path, "data_uri")
    if key in _cache:
        return _cache[key]
    try:
        raw = path.read_bytes()
    except OSError:
        if warnings is not None:
            warnings.append(f"missing file: {path}")
        return None

    suffix = path.suffix
    if suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"):
        raw, suffix = _shrink(raw, suffix)

    mime = mimetypes.types_map.get(suffix.lower()) or "application/octet-stream"
    if suffix.lower() == ".svg":
        mime = "image/svg+xml"

    if warnings is not None and len(raw) > LARGE_ASSET_WARN:
        warnings.append(
            f"{path.name} is {len(raw)/1e6:.1f} MB after processing — "
            "the deck will be large; consider resizing it"
        )

    uri = f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")
    _cache[key] = uri
    return uri


def qr_data_uri(text: str) -> str | None:
    """A QR code as an SVG data URI, used as the offline fallback for an
    external embed. SVG keeps it tiny and sharp at any projector size."""
    key = ("qr", text)
    if key in _cache:
        return _cache[key]
    try:
        import qrcode  # type: ignore
        import qrcode.image.svg  # type: ignore
    except ImportError:
        return None
    try:
        img = qrcode.make(
            text,
            image_factory=qrcode.image.svg.SvgPathImage,
            border=1,
        )
        import io

        buf = io.BytesIO()
        img.save(buf)
        uri = "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
        _cache[key] = uri
        return uri
    except Exception:
        return None


def _resolve(base: Path, src: str) -> Path:
    p = Path(src)
    return p if p.is_absolute() else (base / p)


def _inline_image(node: dict[str, Any], base: Path, warnings: list[str]) -> None:
    src = node.get("src")
    if not isinstance(src, str) or not src:
        return
    if is_data_uri(src):
        return
    if is_external(src):
        # Remote images would break the offline guarantee silently, so say so.
        warnings.append(f"image uses a remote URL and needs network: {src}")
        node["remote"] = True
        return
    uri = data_uri(_resolve(base, src), warnings)
    if uri:
        node["src"] = uri
        node["embedded"] = True


def _inline_media(node: dict[str, Any], base: Path, warnings: list[str]) -> None:
    """Prepare an iframe region.

    Three sources, in order of preference for offline use:
      file   — a local .html activity, inlined as srcdoc
      srcdoc — inline markup written straight into slides.json
      src    — an external URL (YouTube and friends); needs the network
    """
    if node.get("file"):
        path = _resolve(base, str(node["file"]))
        try:
            node["srcdoc"] = path.read_text(encoding="utf-8")
            node["embedded"] = True
            node.pop("file", None)
        except OSError:
            warnings.append(f"missing activity file: {path}")
        return

    if node.get("srcdoc"):
        node["embedded"] = True
        return

    src = node.get("src")
    if isinstance(src, str) and is_external(src):
        node["external"] = True
        qr = qr_data_uri(src)
        if qr:
            node["qr"] = qr
        host = urlparse(src).netloc or src
        node.setdefault("fallback_label", host)


def prepare_slides(
    slides: list[dict[str, Any]], base: Path
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return a copy of the slides with all local media inlined.

    `base` is the directory that relative paths in slides.json resolve against
    — normally the project root, so "images/foo.jpg" means what it looks like.
    """
    import copy

    out = copy.deepcopy(slides)
    warnings: list[str] = []

    for index, slide in enumerate(out, start=1):
        n = slide.get("n", index)
        before = len(warnings)

        if isinstance(slide.get("image"), dict):
            _inline_image(slide["image"], base, warnings)

        for img in slide.get("images") or []:
            if isinstance(img, dict):
                _inline_image(img, base, warnings)

        for region in ("left", "right"):
            block = slide.get(region)
            if isinstance(block, dict):
                if isinstance(block.get("image"), dict):
                    _inline_image(block["image"], base, warnings)
                if isinstance(block.get("media"), dict):
                    _inline_media(block["media"], base, warnings)

        if isinstance(slide.get("media"), dict):
            _inline_media(slide["media"], base, warnings)

        # Attribute any warning this slide produced, so the message is useful.
        for i in range(before, len(warnings)):
            warnings[i] = f"slide {n}: {warnings[i]}"

    return out, warnings


def external_media(slides: list[dict[str, Any]]) -> list[tuple[Any, str]]:
    """Every slide that will need live internet, for the build-time report."""
    found = []
    for position, slide in enumerate(slides, start=1):
        slide.setdefault("n", position)
        for node in (
            slide.get("media"),
            (slide.get("left") or {}).get("media") if isinstance(slide.get("left"), dict) else None,
            (slide.get("right") or {}).get("media") if isinstance(slide.get("right"), dict) else None,
        ):
            if isinstance(node, dict) and node.get("external") and node.get("src"):
                found.append((slide.get("n", "?"), node["src"]))
        img = slide.get("image")
        if isinstance(img, dict) and img.get("remote"):
            found.append((slide.get("n", "?"), img.get("src", "")))
    return found
