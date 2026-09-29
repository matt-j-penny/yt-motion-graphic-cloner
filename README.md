# YT Motion Graphic Cloner

Turn a slice of a YouTube video into an editable HyperFrames motion-graphic template.

## Install with an agent

Paste this repo into Cursor or Claude Code: [github.com/matt-j-penny/yt-motion-graphic-cloner](https://github.com/matt-j-penny/yt-motion-graphic-cloner), then say **setup**.

The agent will:

1. Turn on the Mac helper (it stays on after that)
2. Connect Claude Code so **Make template** can rebuild the graphic
3. Put captured templates in your HyperFrames library
4. Walk you through loading the Chrome extension (one click you have to do yourself)

## Load the Chrome extension

1. Go to `chrome://extensions`
2. Turn on **Developer mode**
3. **Load unpacked** and choose the `extension` folder in this project

On YouTube, click the small button next to the title, mark Start and End, then **Make template**.

Templates land in `Documents/CC/Hyperframes/Assets/templates/captured` and show up in your template library.

## Manual helper (no agent)

Double-click `macos/Install Helper.command`. Same helper the agent installs.
