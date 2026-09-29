from __future__ import annotations

import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps

NOISE = {
    "subscribe",
    "join",
    "share",
    "like",
    "comments",
    "views",
    "youtube",
    "watch later",
}


def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255


def _quantize(img: Image.Image, colors: int = 6) -> list[tuple[tuple[int, int, int], int]]:
    reduced = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=colors)
    palette = reduced.getpalette() or []
    counts = Counter(reduced.getdata())
    ranked = []
    for index, count in counts.most_common():
        if index * 3 + 2 >= len(palette):
            continue
        rgb = (palette[index * 3], palette[index * 3 + 1], palette[index * 3 + 2])
        ranked.append((rgb, count))
    return ranked


def _sample_frame(path: Path) -> dict:
    img = Image.open(path).convert("RGB")
    small = img.resize((160, 90))
    pixels = list(small.getdata())
    lum = sum(_luminance(p) for p in pixels) / max(len(pixels), 1)
    mean = tuple(sum(p[i] for p in pixels) / len(pixels) for i in range(3))
    var = sum(sum((p[i] - mean[i]) ** 2 for i in range(3)) for p in pixels) / max(len(pixels), 1)
    ranked = _quantize(small)
    bg = ranked[0][0] if ranked else (20, 20, 20)
    accents = []
    for rgb, _ in ranked[1:]:
        mx, mn = max(rgb), min(rgb)
        sat = (mx - mn) / 255
        if sat > 0.18:
            accents.append((sat, rgb))
    accents.sort(reverse=True)
    accent = accents[0][1] if accents else (200, 70, 70)
    # bottom third brightness — lower-thirds sit here
    w, h = small.size
    bottom = list(small.crop((0, int(h * 0.62), w, h)).getdata())
    bottom_lum = sum(_luminance(p) for p in bottom) / max(len(bottom), 1)
    return {
        "lum": lum,
        "var": var,
        "bg": bg,
        "accent": accent,
        "bottom_lum": bottom_lum,
        "light_text": lum < 0.45,
    }


def _ocr_frame(path: Path) -> list[str]:
    if not shutil.which("tesseract"):
        return []
    img = Image.open(path).convert("RGB")
    work = ImageOps.autocontrast(img)
    tmp = path.parent / "_ocr.jpg"
    work.save(tmp, quality=92)
    lines: list[str] = []
    try:
        result = subprocess.run(
            ["tesseract", str(tmp), "stdout", "--psm", "6"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        lines = _parse_ocr(result.stdout or "")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        lines = []
    tmp.unlink(missing_ok=True)
    return lines


def _parse_ocr(raw: str) -> list[str]:
    lines = []
    for row in raw.splitlines():
        line = re.sub(r"\s+", " ", row).strip()
        line = re.sub(r"^[\W\d|_]+", "", line).strip()
        if len(line) < 4:
            continue
        if line.lower() in NOISE:
            continue
        if not re.search(r"[A-Za-z]{3,}", line):
            continue
        lines.append(line)
    return lines


def _clean_lines(lines: list[str]) -> list[str]:
    seen = set()
    out = []
    for line in lines:
        key = re.sub(r"[^a-z0-9]+", "", line.lower())
        if key in seen or len(key) < 4:
            continue
        seen.add(key)
        out.append(line)
    return out


def _split_title_and_items(lines: list[str]) -> tuple[str, list[str]]:
    if not lines:
        return "Headline", []
    keep_title = re.compile(r"report|guide|study|goals|plan|update|review", re.I)
    title_parts = []
    items = []
    for line in lines:
        looks_item = (
            bool(title_parts)
            and len(line.split()) <= 4
            and len(line) <= 26
            and not keep_title.search(line)
        )
        if looks_item:
            items.append(line)
        else:
            title_parts.append(line)
    if not title_parts:
        return lines[0], lines[1:]
    headline = " ".join(title_parts[:2])
    if len(headline) > 90:
        headline = title_parts[0]
        items = title_parts[1:] + items
    return headline, items[:6]


def classify(stats: dict, lines: list[str]) -> str:
    blob = " ".join(lines)
    takeover = stats["var"] < 2200
    has_stat = bool(re.search(r"(\d[\d,\.]*\s?%|\$\s?\d[\d,\.]*)", blob))
    if has_stat and len(lines) <= 3:
        return "stat"
    if not takeover and stats["bottom_lum"] + 0.08 < stats["lum"]:
        return "lower_third"
    if len(lines) >= 3:
        return "callout_stack"
    if not takeover:
        return "lower_third"
    return "kinetic_title"


def analyze_frames(frames: list[Path], duration: float, title: str) -> dict:
    if not frames:
        raise RuntimeError("No screens were saved, so a template couldn’t be built.")
    stats = _sample_frame(frames[-1])
    lines = _clean_lines(_ocr_frame(frames[-1]))
    if len(lines) < 2 and len(frames) > 2:
        extra = _ocr_frame(frames[len(frames) // 2])
        lines = _clean_lines(lines + extra)
    if not lines:
        words = [w for w in re.split(r"\s+", title or "") if w]
        lines = [" ".join(words[:8])] if words else ["Headline"]
    headline, items = _split_title_and_items(lines)
    kind = classify(stats, [headline, *items])
    if kind == "callout_stack" and len(items) < 2:
        kind = "kinetic_title"
    return {
        "kind": kind,
        "duration": max(3.0, min(float(duration), 12.0)),
        "headline": headline,
        "items": items,
        "bg": stats["bg"],
        "accent": stats["accent"],
        "light_text": stats["light_text"],
        "takeover": stats["var"] < 2200,
    }
