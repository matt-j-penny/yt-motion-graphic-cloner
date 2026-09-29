---
name: setup
description: >
  Install YT Motion Capture on a Mac: Chrome extension, local helper, Claude Code
  connection, ffmpeg/yt-dlp, and HyperFrames template library folders. Use when
  the user asks to set up, install, get this working, connect Claude, load the
  extension, or fix the helper.
user-invocable: true
---

# Set up YT Motion Capture

Run the installer. Do not skip steps. Talk to the person in short, plain sentences.

## 1. Install

From the repo root (or `${CLAUDE_PLUGIN_ROOT}` if this is an installed plugin):

```bash
python3 scripts/setup.py
```

The script:

- installs `ffmpeg` and `yt-dlp` with Homebrew if needed
- installs Claude Code if it is missing
- creates `~/Documents/CC/Hyperframes` library folders
- hooks captured templates into `template-library.html` when that file exists
- starts the Mac helper (stays on after restart)
- opens the `extension` folder and Chrome’s extensions page

## 2. Read the JSON it prints

Treat `"ok": true` as the tools being ready. `"next"` is what you still tell the person.

- `claude: false` → they need Claude Code. Point them to https://claude.ai/download
- `claudeLoggedIn: false` → ask them to run `claude auth login` in Terminal, then re-run `python3 scripts/setup.py --check`
- `helper: false` → run setup again. If it still fails, read `~/Library/Logs/yt-motion-capture.log`
- `libraryWired: false` and they already have a template library → say captured graphics may not show in the library page yet, but files still save under `libraryDir`

## 3. Chrome extension (you cannot finish this click for them)

They must:

1. Open `chrome://extensions`
2. Turn **Developer mode** on (top right)
3. Click **Load unpacked**
4. Choose the `extension` folder printed as `"extension"` in the JSON

Then tell them: open any YouTube video, click the small button next to the title, mark Start and End, then **Make template**.

## 4. Confirm

```bash
python3 scripts/setup.py --check
```

Ready means helper is on, Claude is signed in, ffmpeg and yt-dlp are present, and templates save to `~/Documents/CC/Hyperframes/Assets/templates/captured`.

Do not leave them with a wall of terminal output. Say what’s done, what’s left (usually the Chrome load-unpacked click), and where templates will show up.
