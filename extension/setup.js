const helperEl = document.getElementById("helper");
const detailEl = document.getElementById("detail");

async function check() {
  const result = await chrome.runtime.sendMessage({ type: "forward", path: "/health" });
  if (!result?.ok) {
    helperEl.innerHTML = '<span class="wait">Helper is off.</span> Ask your agent to run setup.';
    detailEl.textContent = "";
    return;
  }
  const data = result.data || {};
  const missing = [];
  if (!data.ytdlp) missing.push("yt-dlp");
  if (!data.ffmpeg) missing.push("ffmpeg");
  if (data.claude === false) missing.push("Claude Code");
  helperEl.innerHTML = '<span class="ok">Helper is on.</span> You can go back to YouTube.';
  if (missing.length) {
    detailEl.textContent = "Still missing " + missing.join(" and ") + ". Ask your agent to run setup again.";
  } else if (data.libraryDir) {
    detailEl.textContent = "Templates save in your HyperFrames library.";
  } else {
    detailEl.textContent = "";
  }
}

document.getElementById("retry").addEventListener("click", check);
check();
