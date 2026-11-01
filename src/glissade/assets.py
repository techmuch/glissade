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
import mimetypes
from collections.abc import Iterator
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

# QR codes keyed by their text; tiny and few.
_cache: dict[tuple, str] = {}
# Inlined files keyed by path, holding the (mtime, size) they were read at.
# One entry per path, so a long `start --watch` session that keeps swapping
# an image replaces its entry rather than piling up every version.
_files: dict[str, tuple[tuple, str]] = {}

# Types the platform's mimetypes table may not know, which matter here: an
# SVG or a web font served as octet-stream is silently ignored by browsers.
_EXTRA_MIME = {
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".webp": "image/webp",
}


def is_external(src: str) -> bool:
    """True for anything the browser must fetch over the network."""
    if not isinstance(src, str):
        return False
    return src.startswith(("http://", "https://", "//"))


def is_data_uri(src: str) -> bool:
    return isinstance(src, str) and src.startswith("data:")


def _stamp(path: Path) -> tuple:
    try:
        st = path.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return (None, None)


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
    key, stamp = str(path), _stamp(path)
    hit = _files.get(key)
    if hit and hit[0] == stamp:
        return hit[1]
    try:
        raw = path.read_bytes()
    except OSError:
        if warnings is not None:
            warnings.append(f"missing file: {path}")
        return None

    suffix = path.suffix
    if suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"):
        raw, suffix = _shrink(raw, suffix)

    mime = (
        _EXTRA_MIME.get(suffix.lower())
        or mimetypes.types_map.get(suffix.lower())
        or "application/octet-stream"
    )

    if warnings is not None and len(raw) > LARGE_ASSET_WARN:
        warnings.append(
            f"{path.name} is {len(raw)/1e6:.1f} MB after processing — "
            "the deck will be large; consider resizing it"
        )

    uri = f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")
    _files[key] = (stamp, uri)
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


def media_nodes(slide: Any) -> Iterator[tuple[str, str, dict[str, Any]]]:
    """Every image and media object a slide holds, wherever it sits.

    Yields `(kind, where, node)`: kind is "image" or "media", `where` is a
    short location suffix (" left", " quad 2", " card 1" ...; empty for the
    slide itself). This is the one list of places media can live — inlining,
    the offline report and `check --fix` all walk it, so a new layout that
    holds media only has to be taught here.
    """
    if not isinstance(slide, dict):
        return

    def pair(owner: Any, where: str):
        if not isinstance(owner, dict):
            return
        if isinstance(owner.get("image"), dict):
            yield "image", where, owner["image"]
        if isinstance(owner.get("media"), dict):
            yield "media", where, owner["media"]

    yield from pair(slide, "")
    for i, img in enumerate(slide.get("images") or [], start=1):
        if isinstance(img, dict):
            yield "image", f" image {i}", img
    for i, card in enumerate(slide.get("cards") or [], start=1):
        yield from pair(card, f" card {i}")
    for side in ("left", "right"):
        yield from pair(slide.get(side), f" {side}")
    for i, quad in enumerate(slide.get("quads") or [], start=1):
        yield from pair(quad, f" quad {i}")


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
        if not isinstance(slide, dict):
            continue
        n = slide.get("n", index)
        before = len(warnings)

        for kind, _, node in media_nodes(slide):
            if kind == "image":
                _inline_image(node, base, warnings)
            else:
                _inline_media(node, base, warnings)

        # Attribute any warning this slide produced, so the message is useful.
        for i in range(before, len(warnings)):
            warnings[i] = f"slide {n}: {warnings[i]}"

    return out, warnings


def external_media(slides: list[dict[str, Any]]) -> list[tuple[Any, str]]:
    """Every slide that will need live internet, for the build-time report."""
    found = []
    for position, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            continue
        n = slide.get("n", position)
        for kind, _, node in media_nodes(slide):
            if kind == "media" and node.get("external") and node.get("src"):
                found.append((n, node["src"]))
            elif kind == "image" and node.get("remote"):
                found.append((n, node.get("src", "")))
    return found
