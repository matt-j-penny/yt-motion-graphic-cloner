#!/usr/bin/env python3
"""Install and check YT Motion Capture. Safe for an agent to run."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parent.parent)
if not (ROOT / "helper" / "server.py").exists():
    ROOT = Path(__file__).resolve().parent.parent

HELPER = ROOT / "helper"
EXTENSION = ROOT / "extension"
HOME = Path.home()
LABEL = "com.ytmotioncapture.helper"
PLIST = HOME / "Library/LaunchAgents" / f"{LABEL}.plist"
LOG = HOME / "Library/Logs/yt-motion-capture.log"
HEALTH = "http://127.0.0.1:47821/health"
HYPERFRAMES = HOME / "Documents/CC/Hyperframes"
INBOX = HYPERFRAMES / "captures/inbox"
LIBRARY = HYPERFRAMES / "Assets/templates/captured"
CATALOG_JSON = HYPERFRAMES / "captures/captured-templates.json"
CATALOG_JS = HYPERFRAMES / "captures/captured-templates.js"
LIBRARY_PAGE = HYPERFRAMES / "template-library.html"
CLAUDE_INSTALL = "https://claude.ai/install.sh"


def which(name: str) -> str | None:
    extra = [str(HOME / ".local/bin"), "/opt/homebrew/bin", "/usr/local/bin"]
    path = os.environ.get("PATH", "")
    os.environ["PATH"] = ":".join(extra + [path])
    return shutil.which(name)


def run(cmd: list[str], timeout: int = 180, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, timeout=timeout, capture_output=True, text=True, check=check)


def brew_bin() -> str | None:
    return which("brew")


def install_brew_pkg(name: str) -> str | None:
    brew = brew_bin()
    if not brew:
        return "Homebrew is missing, so that tool can’t be installed automatically."
    if which(name):
        return None
    result = run([brew, "install", name], timeout=600)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip().splitlines()
        return tail[-1][:200] if tail else f"Couldn’t install {name}."
    return None


def claude_logged_in() -> bool | None:
    binary = which("claude")
    if not binary:
        return None
    result = run([binary, "auth", "status"], timeout=20)
    raw = (result.stdout or result.stderr or "").strip()
    try:
        data = json.loads(raw[raw.find("{") : raw.rfind("}") + 1] if "{" in raw else raw)
        return bool(data.get("loggedIn"))
    except json.JSONDecodeError:
        return result.returncode == 0


def install_claude() -> str | None:
    if which("claude"):
        return None
    result = run(
        ["/bin/bash", "-lc", f"curl -fsSL {CLAUDE_INSTALL} | bash"],
        timeout=300,
    )
    if which("claude"):
        return None
    tail = (result.stderr or result.stdout or "").strip().splitlines()
    return tail[-1][:240] if tail else "Claude Code didn’t install. Open https://claude.ai/download and try again."


def ensure_library() -> dict:
    INBOX.mkdir(parents=True, exist_ok=True)
    LIBRARY.mkdir(parents=True, exist_ok=True)
    CATALOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    if not CATALOG_JSON.exists():
        CATALOG_JSON.write_text("[]\n", encoding="utf-8")
    if not CATALOG_JS.exists():
        CATALOG_JS.write_text("window.CAPTURED_TEMPLATES = [];\n", encoding="utf-8")
    wired = False
    if LIBRARY_PAGE.exists():
        html = LIBRARY_PAGE.read_text(encoding="utf-8")
        original = html
        if "captured-templates.js" not in html and "const TEMPLATES" in html:
            html = html.replace(
                "<script>\nconst TEMPLATES",
                '<script src="captures/captured-templates.js"></script>\n<script>\nconst TEMPLATES',
                1,
            )
            if html == original:
                html = html.replace(
                    "<script>const TEMPLATES",
                    '<script src="captures/captured-templates.js"></script>\n<script>const TEMPLATES',
                    1,
                )
        if "CAPTURED_TEMPLATES" not in html:
            snippet = (
                "\nif (Array.isArray(window.CAPTURED_TEMPLATES)) {\n"
                "  TEMPLATES.unshift(...window.CAPTURED_TEMPLATES);\n"
                "}\n"
            )
            if "// ── RENDER" in html:
                html = html.replace("// ── RENDER", snippet + "\n// ── RENDER", 1)
            elif "function mediaBadgeHtml" in html:
                html = html.replace("function mediaBadgeHtml", snippet + "function mediaBadgeHtml", 1)
        if html != original:
            LIBRARY_PAGE.write_text(html, encoding="utf-8")
        wired = "captured-templates.js" in html and "CAPTURED_TEMPLATES" in html
    return {
        "libraryRoot": str(HYPERFRAMES),
        "libraryDir": str(LIBRARY),
        "inbox": str(INBOX),
        "libraryWired": wired,
        "libraryPage": str(LIBRARY_PAGE) if LIBRARY_PAGE.exists() else None,
    }


def write_plist() -> None:
    python = which("python3")
    if not python:
        raise RuntimeError("Python 3 is missing.")
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    path = ":".join(
        [str(HOME / ".local/bin"), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
    )
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{python}</string>
    <string>{HELPER / "server.py"}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>{HELPER}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>{LOG}</string>
  <key>StandardErrorPath</key>
  <string>{LOG}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>{path}</string>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
  </dict>
</dict>
</plist>
"""
    PLIST.write_text(plist, encoding="utf-8")


def restart_helper() -> bool:
    uid = os.getuid()
    run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"])
    run(["launchctl", "bootstrap", f"gui/{uid}", str(PLIST)], check=False)
    run(["launchctl", "kickstart", "-k", f"gui/{uid}/{LABEL}"])
    for _ in range(20):
        try:
            with urllib.request.urlopen(HEALTH, timeout=1) as response:
                if response.status == 200:
                    return True
        except OSError:
            time.sleep(0.4)
    return False


def health() -> dict | None:
    try:
        with urllib.request.urlopen(HEALTH, timeout=2) as response:
            return json.loads(response.read().decode("utf-8"))
    except OSError:
        return None


def open_chrome_steps() -> None:
    run(["open", str(EXTENSION)])
    run(
        [
            "osascript",
            "-e",
            'tell application "Google Chrome" to open location "chrome://extensions/"',
        ]
    )


def report(check_only: bool) -> dict:
    lib = {
        "libraryRoot": str(HYPERFRAMES),
        "libraryDir": str(LIBRARY),
        "inbox": str(INBOX),
        "libraryReady": LIBRARY.exists(),
        "catalogReady": CATALOG_JS.exists(),
        "libraryWired": False,
        "libraryPage": str(LIBRARY_PAGE) if LIBRARY_PAGE.exists() else None,
    }
    if LIBRARY_PAGE.exists():
        html = LIBRARY_PAGE.read_text(encoding="utf-8")
        lib["libraryWired"] = "captured-templates.js" in html and "CAPTURED_TEMPLATES" in html
    live = health() or {}
    data = {
        "ok": False,
        "macos": sys.platform == "darwin",
        "repo": str(ROOT),
        "extension": str(EXTENSION),
        "python": bool(which("python3")),
        "brew": bool(brew_bin()),
        "ffmpeg": bool(which("ffmpeg")),
        "ytdlp": bool(which("yt-dlp")),
        "claude": bool(which("claude")),
        "claudeLoggedIn": claude_logged_in(),
        "helper": bool(live),
        "helperVersion": live.get("version"),
        **lib,
        "next": [],
    }
    if live:
        data["libraryWired"] = bool(live.get("libraryWired", data["libraryWired"]))
        data["libraryReady"] = bool(live.get("libraryReady", data["libraryReady"]))
    ready = all(
        [
            data["macos"],
            data["python"],
            data["ffmpeg"],
            data["ytdlp"],
            data["claude"],
            data["claudeLoggedIn"] is not False,
            data["helper"],
            data["libraryReady"],
            data["catalogReady"],
        ]
    )
    data["ok"] = ready
    if not data["macos"]:
        data["next"].append("This helper only runs on a Mac.")
    if not data["ffmpeg"] or not data["ytdlp"]:
        data["next"].append("Install ffmpeg and yt-dlp with Homebrew.")
    if not data["claude"]:
        data["next"].append("Install Claude Code from https://claude.ai/download")
    elif data["claudeLoggedIn"] is False:
        data["next"].append("Sign Claude Code in: run `claude auth login` in Terminal.")
    if not data["helper"]:
        data["next"].append("The Mac helper isn’t running yet.")
    if EXTENSION.exists():
        data["next"].append(
            "In Chrome: chrome://extensions → Developer mode on → Load unpacked → choose the extension folder."
        )
    if check_only:
        data["next"] = data["next"] if not ready else ["Ready. Load the Chrome extension if you haven’t yet."]
    return data


def setup(helper_only: bool) -> dict:
    if sys.platform != "darwin":
        return {"ok": False, "error": "This only works on a Mac.", "next": []}
    if not which("python3"):
        return {"ok": False, "error": "Python 3 is missing.", "next": []}

    notes: list[str] = []
    if not helper_only:
        if not brew_bin():
            notes.append("Homebrew is missing. Install it from https://brew.sh then run setup again.")
        else:
            for pkg in ("ffmpeg", "yt-dlp"):
                err = install_brew_pkg(pkg)
                if err:
                    notes.append(err)
        err = install_claude()
        if err:
            notes.append(err)
        if which("claude") and claude_logged_in() is False:
            notes.append("Claude Code is installed but not signed in. Ask them to run: claude auth login")

    lib = ensure_library()
    write_plist()
    helper_up = restart_helper()
    if not helper_up:
        notes.append("The helper didn’t start. Try running setup again.")
    if helper_only:
        return {
            "ok": helper_up,
            "helper": helper_up,
            "notes": notes,
            **lib,
        }
    try:
        open_chrome_steps()
    except OSError:
        pass
    data = report(check_only=False)
    data["notes"] = notes
    data.update(lib)
    data["helper"] = helper_up
    if helper_up and data["claude"] and data["claudeLoggedIn"] is not False:
        data["ok"] = bool(data["ffmpeg"] and data["ytdlp"] and data["libraryReady"])
    return data


def main() -> int:
    args = set(sys.argv[1:])
    check_only = "--check" in args
    helper_only = "--helper-only" in args
    if check_only:
        data = report(check_only=True)
    else:
        data = setup(helper_only=helper_only)
    print(json.dumps(data, indent=2))
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
