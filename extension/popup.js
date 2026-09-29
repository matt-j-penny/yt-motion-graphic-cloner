const statusEl = document.getElementById("status");
const detailEl = document.getElementById("detail");

async function refresh() {
  const result = await chrome.runtime.sendMessage({ type: "forward", path: "/health" });
  if (!result?.ok) {
    statusEl.textContent = "Helper is off";
    detailEl.textContent = "Set it up once. After that it starts with your Mac.";
    return;
  }
  const missing = [];
  if (!result.data.ytdlp) missing.push("yt-dlp");
  if (!result.data.ffmpeg) missing.push("ffmpeg");
  if (result.data.claude === false) missing.push("Claude Code");
  statusEl.textContent = "Helper is on";
  if (missing.length) {
    detailEl.textContent = `Missing ${missing.join(" and ")}. Ask your agent to run setup.`;
  } else {
    detailEl.textContent = "Ready. Templates save in your HyperFrames library.";
  }
}

document.getElementById("setup").addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "open-setup" });
});

document.getElementById("inbox").addEventListener("click", async () => {
  await chrome.runtime.sendMessage({
    type: "forward",
    path: "/open-inbox",
    options: { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" },
  });
});

refresh();
