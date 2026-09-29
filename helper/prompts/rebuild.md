You are rebuilding a motion graphic from sequential video stills as a HyperFrames HTML composition.

## Input
- `frames/` contains JPEG stills in time order, taken at 4 frames per second or more. Filenames are `frame_0001.jpg`, `frame_0002.jpg`, …
- `frames.json` lists every still with its timestamp. Read all of them.
- `contact-sheet.jpg` is a grid of every still, if present.
- `capture.json` has the YouTube title, start, end, and duration.

You MUST look at the stills. Read `contact-sheet.jpg` first, then read every file in `frames/` in order. Do not skip frames. Do not invent a generic title card. Recreate the actual graphic: layout, colors, type, icons, connectors, and the order things appear.

## Output
Write one file: `template.html` in this same folder. It must be a complete standalone HyperFrames composition.

Requirements:
- Root `#root` with `data-composition-id="main"`, `data-width="1920"`, `data-height="1080"`, `data-duration` matching the clip length, `data-start="0"`.
- `#root` uses `width: 100%; height: 100%` (Studio stamps the pixel size).
- Timed sections use `class="clip"` plus `data-start` and `data-duration`.
- One paused GSAP timeline registered as `window.__timelines["main"]`.
- Load GSAP from `https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js`.
- Recreate the motion: what enters, when, how it holds, how later pieces arrive. Time it from the 4fps stills.
- Make copy easy to edit (clear text in the HTML).
- Do not tween `autoAlpha` / `visibility` on a `.clip` node; animate inner nodes.
- Do not set a CSS `transform` on a node you then GSAP `x`/`y`/`scale`/`rotation`.
- Do not use `<br>` in body copy; use block elements.
- Do not add an autoplay helper that calls `eventCallback` unless you first check `typeof t.eventCallback === "function"`. Prefer no autoplay script at all.
- Do not copy or embed the original YouTube footage. Rebuild in HTML/CSS/SVG/GSAP.

When the file is written, stop. Do not ask questions.
