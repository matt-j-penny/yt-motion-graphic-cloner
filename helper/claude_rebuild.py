from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from config import CLAUDE_TIMEOUT, HOME, MIN_FPS

PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "rebuild.md"


def claude_bin() -> str | None:
    extra = [
        str(HOME / ".local/bin"),
        "/opt/homebrew/bin",
        "/usr/local/bin",
    ]
    path = os.environ.get("PATH", "")
    os.environ["PATH"] = ":".join(extra + [path])
    return shutil.which("claude")


def tool_has_claude() -> bool:
    return bool(claude_bin())


def _extract_html(text: str) -> str | None:
    lower = text.lower()
    start = lower.find("<!doctype")
    if start < 0:
        start = lower.find("<html")
    if start < 0:
        return None
    end = lower.rfind("</html>")
    if end < 0:
        return None
    return text[start : end + len("</html>")]


def rebuild_with_claude(dest: Path, frames: list[Path], duration: float, title: str, on_status) -> str:
    binary = claude_bin()
    if not binary:
        raise RuntimeError("Claude Code isn’t installed, so the graphic can’t be rebuilt yet.")
    if not frames:
        raise RuntimeError("No screens were saved, so Claude had nothing to look at.")

    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    listing = []
    fps = len(frames) / max(duration, 0.01)
    for index, frame in enumerate(frames):
        rel = f"frames/{frame.name}" if frame.parent.name == "frames" else frame.name
        listing.append(f"- {rel}  ({index / max(fps, MIN_FPS):.2f}s)")
    prompt += (
        f"\n\nClip: {title}\n"
        f"Duration: {duration:.2f}s\n"
        f"Stills: {len(frames)} files at {fps:.1f} per second (must be at least {MIN_FPS}).\n"
        f"Read every still in order. Do not skip any:\n" + "\n".join(listing) + "\n"
    )
    (dest / "rebuild-prompt.md").write_text(prompt, encoding="utf-8")

    on_status(f"Asking Claude to rebuild from {len(frames)} stills…")
    cmd = [
        binary,
        "-p",
        prompt,
        "--output-format",
        "text",
        "--permission-mode",
        "bypassPermissions",
        "--dangerously-skip-permissions",
        "--add-dir",
        str(dest),
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(dest),
            timeout=CLAUDE_TIMEOUT,
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(HOME)},
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Claude took too long and was stopped.") from exc

    html_path = dest / "template.html"
    if html_path.exists() and html_path.stat().st_size > 200:
        return html_path.read_text(encoding="utf-8")

    dumped = (result.stdout or "") + "\n" + (result.stderr or "")
    html = _extract_html(result.stdout or "")
    if html:
        html_path.write_text(html, encoding="utf-8")
        return html
    tail = dumped.strip().splitlines()[-8:] if dumped.strip() else ["no output"]
    raise RuntimeError("Claude didn’t write a template. " + " ".join(tail)[:280])
